from concurrent.futures import ThreadPoolExecutor

import pytest
from app.core.security import decode_access_token
from app.domain.errors import AppError, EmailTakenError
from app.api.deps import get_current_user
from fastapi import HTTPException
from app.core.rate_limit import check_login
from app.services import auth_service

pytestmark = pytest.mark.integration


def test_authentication_and_private_profile_api_end_to_end(api_client):
    registration = api_client.post(
        "/api/v1/auth/register",
        json={
            "name": "Integrated Alice",
            "email": " Integrated@Example.com ",
            "password": "correct-horse-battery",
        },
    )
    assert registration.status_code == 201
    token = registration.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    duplicate = api_client.post(
        "/api/v1/auth/register",
        json={
            "name": "Another Alice",
            "email": "integrated@example.com",
            "password": "another-long-password",
        },
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "EMAIL_TAKEN"

    own_profile = api_client.get("/api/v1/users/me", headers=headers)
    assert own_profile.status_code == 200
    assert own_profile.json()["email"] == "integrated@example.com"

    user_id = own_profile.json()["id"]
    public_profile = api_client.get(f"/api/v1/users/{user_id}", headers=headers)
    assert public_profile.status_code == 200
    assert set(public_profile.json()) == {"id", "name", "source"}
    search = api_client.get("/api/v1/users/search?q=Integrated", headers=headers)
    assert search.status_code == 200
    assert search.json()[0]["id"] == user_id
    assert "email" not in search.text

    login = api_client.post(
        "/api/v1/auth/token",
        data={
            "username": "INTEGRATED@example.com",
            "password": "correct-horse-battery",
        },
    )
    assert login.status_code == 200
    assert login.json()["token_type"] == "bearer"


def test_registration_normalizes_email_and_maps_uniqueness(clean_graph):
    driver, redis_client = clean_graph
    auth_service.register(
        driver,
        redis_client,
        client_ip="192.0.2.1",
        name="Alice",
        email=" Alice@Example.com ",
        password="correct-horse-battery",
    )
    with pytest.raises(EmailTakenError):
        auth_service.register(
            driver,
            redis_client,
            client_ip="192.0.2.2",
            name="Another Alice",
            email="alice@example.COM",
            password="another-correct-password",
        )
    with driver.session() as session:
        assert session.run("MATCH (a:Account) RETURN count(a) AS n").single()["n"] == 1


def test_concurrent_same_email_registration_has_one_winner(clean_graph):
    driver, redis_client = clean_graph

    def register(index):
        try:
            auth_service.register(
                driver,
                redis_client,
                client_ip=f"192.0.2.{index + 1}",
                name=f"Candidate {index}",
                email="race@example.com",
                password="distinct-and-valid-password",
            )
            return "created"
        except EmailTakenError:
            return "duplicate"

    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(register, range(20)))
    assert results.count("created") == 1
    assert results.count("duplicate") == 19
    with driver.session() as session:
        assert session.run("MATCH (u:User) RETURN count(u) AS n").single()["n"] == 1
        assert session.run("MATCH (a:Account) RETURN count(a) AS n").single()["n"] == 1


def test_dropping_email_constraint_breaks_concurrent_registration_invariant(
    clean_graph,
):
    """Deliberately remove the unique constraint and prove duplicate registration wins.

    The dedicated integration database is cleared and its schema restored in finally,
    even if the mutation assertion fails.
    """
    from app.db.schema import ensure_schema

    driver, redis_client = clean_graph
    with driver.session() as session:
        session.run("DROP CONSTRAINT account_email_unique IF EXISTS").consume()

    def register(index):
        try:
            auth_service.register(
                driver,
                redis_client,
                client_ip=f"198.51.100.{index + 1}",
                name=f"Mutation Candidate {index}",
                email="mutated-race@example.com",
                password="distinct-and-valid-password",
            )
            return "created"
        except EmailTakenError:
            return "duplicate"

    try:
        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(register, range(8)))
        # The regular concurrency test asserts exactly one create. Without the
        # constraint, this same invariant is broken and all registrations succeed.
        with pytest.raises(AssertionError):
            assert results.count("created") == 1
        assert results.count("created") > 1
        with driver.session() as session:
            assert (
                session.run("MATCH (a:Account) RETURN count(a) AS n").single()["n"] > 1
            )
    finally:
        with driver.session() as session:
            session.execute_write(
                lambda tx: tx.run("MATCH (n) DETACH DELETE n").consume()
            )
        ensure_schema(driver)


def test_login_issues_token_and_missing_or_wrong_credentials_match(clean_graph):
    driver, redis_client = clean_graph
    token_response = auth_service.register(
        driver,
        redis_client,
        client_ip="192.0.2.50",
        name="Login User",
        email="login@example.com",
        password="valid-password-for-login",
    )
    claims = decode_access_token(token_response["access_token"])
    assert claims["sub"]
    assert token_response["expires_in"] == 1800

    wrong = []
    for email, password in (
        ("login@example.com", "wrong-password"),
        ("missing@example.com", "wrong-password"),
    ):
        with pytest.raises(AppError) as error:
            auth_service.login(
                driver,
                redis_client,
                client_ip=f"192.0.2.{60 + len(wrong)}",
                email=email,
                password=password,
            )
        wrong.append((error.value.status, error.value.code, error.value.message))
    assert wrong[0] == wrong[1]


def test_accounts_and_credentials_are_separate_from_public_user(clean_graph):
    driver, redis_client = clean_graph
    auth_service.register(
        driver,
        redis_client,
        client_ip="192.0.2.80",
        name="Private Account",
        email="private@example.com",
        password="valid-password-value",
    )
    with driver.session() as session:
        user_record = session.run(
            "MATCH (u:User) RETURN properties(u) AS properties"
        ).single()
        account_record = session.run(
            "MATCH (a:Account) RETURN properties(a) AS properties"
        ).single()
    assert "email" not in user_record["properties"]
    assert "password_hash" not in user_record["properties"]
    assert "email_normalized" in account_record["properties"]
    assert account_record["properties"]["password_hash"].startswith("$argon2id$")


def test_access_token_is_rejected_after_user_deletion(clean_graph):
    driver, redis_client = clean_graph
    token = auth_service.register(
        driver,
        redis_client,
        client_ip="192.0.2.90",
        name="Deleted Later",
        email="deleted@example.com",
        password="valid-password-value",
    )["access_token"]
    assert get_current_user(token=token, driver=driver)["user_id"]
    user_id = decode_access_token(token)["sub"]
    with driver.session() as session:
        session.execute_write(
            lambda tx: tx.run(
                "MATCH (u:User {id: $id}) DETACH DELETE u", id=user_id
            ).consume()
        )
    with pytest.raises(HTTPException) as error:
        get_current_user(token=token, driver=driver)
    assert error.value.status_code == 401


def test_real_redis_login_limit_rejects_sixth_attempt(clean_graph):
    _, redis_client = clean_graph
    for _ in range(5):
        check_login(redis_client, "192.0.2.100", "rate@example.com")
    with pytest.raises(AppError) as error:
        check_login(redis_client, "192.0.2.100", "rate@example.com")
    assert error.value.status == 429
    assert int(error.value.headers["Retry-After"]) > 0
