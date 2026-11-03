from unittest.mock import ANY, Mock, call, patch

import pytest
from fastapi.testclient import TestClient
from neo4j.exceptions import Neo4jError

from app.api.deps import get_current_user
from app.core.security import create_access_token
from app.db.neo4j_db import get_driver
from app.db.redis_cache import get_client
from app.domain.errors import AppError, RateLimitedError
from app.main import app

client = TestClient(app)


class RedisStub:
    def eval(self, *_args):
        return [1, 60]


class BrokenRedis:
    def eval(self, *_args):
        raise OSError("unavailable")


@pytest.fixture
def authenticated_client():
    previous = app.dependency_overrides.copy()
    app.dependency_overrides[get_current_user] = lambda: {"user_id": "test-user"}
    app.dependency_overrides[get_client] = RedisStub
    yield client
    app.dependency_overrides.clear()
    app.dependency_overrides.update(previous)


def _register_payload(**overrides):
    return {
        "name": "Alice",
        "email": "alice@example.com",
        "password": "a-long-password",
        **overrides,
    }


def test_health_check_is_live_without_dependencies():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_removed_user_creation_and_arbitrary_connections_routes():
    assert client.post("/api/v1/users/", json={}).status_code in {404, 405}
    assert client.post(
        "/api/v1/connections", json={"user_id_1": "a", "user_id_2": "b"}
    ).status_code in {404, 405}


def test_register_validates_payload_before_service_call():
    response = client.post(
        "/api/v1/auth/register", json=_register_payload(password="short")
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
    assert all("input" not in item for item in response.json()["error"]["details"])


def test_register_delegates_and_returns_token_contract(monkeypatch):
    previous = app.dependency_overrides.copy()
    app.dependency_overrides[get_driver] = lambda: object()
    app.dependency_overrides[get_client] = RedisStub
    result = {"access_token": "token", "token_type": "bearer", "expires_in": 1800}
    received = {}

    def register(*_args, **kwargs):
        received.update(kwargs)
        return result

    monkeypatch.setattr("app.api.routes_auth.auth_service.register", register)
    response = client.post(
        "/api/v1/auth/register",
        json=_register_payload(),
        headers={"X-Forwarded-For": "198.51.100.55"},
    )
    app.dependency_overrides.clear()
    app.dependency_overrides.update(previous)
    assert response.status_code == 201
    assert response.json() == result
    assert received["client_ip"] == "testclient"


def test_rate_limit_error_uses_http_retry_after_header(monkeypatch):
    previous = app.dependency_overrides.copy()
    app.dependency_overrides[get_client] = RedisStub

    def limited(*_args, **_kwargs):
        raise RateLimitedError(35)

    monkeypatch.setattr("app.api.routes_auth.auth_service.register", limited)
    response = client.post("/api/v1/auth/register", json=_register_payload())
    app.dependency_overrides.clear()
    app.dependency_overrides.update(previous)
    assert response.status_code == 429
    assert response.headers["Retry-After"] == "35"
    assert response.json()["error"]["code"] == "RATE_LIMITED"


def test_unknown_and_wrong_credentials_have_identical_error_envelope(monkeypatch):
    previous = app.dependency_overrides.copy()
    app.dependency_overrides[get_client] = RedisStub

    def invalid_credentials(*_args, **_kwargs):
        raise AppError("UNAUTHENTICATED", "Incorrect email or password.", 401)

    monkeypatch.setattr("app.api.routes_auth.auth_service.login", invalid_credentials)
    headers = {"X-Request-ID": "same-request-id"}
    first = client.post(
        "/api/v1/auth/token",
        data={"username": "known@example.com", "password": "wrong"},
        headers=headers,
    )
    second = client.post(
        "/api/v1/auth/token",
        data={"username": "missing@example.com", "password": "wrong"},
        headers=headers,
    )
    app.dependency_overrides.clear()
    app.dependency_overrides.update(previous)
    assert first.status_code == second.status_code == 401
    assert first.json() == second.json()


def test_login_fails_closed_when_redis_is_unavailable():
    previous = app.dependency_overrides.copy()
    app.dependency_overrides[get_client] = BrokenRedis
    response = client.post(
        "/api/v1/auth/token",
        data={"username": "alice@example.com", "password": "some-password"},
    )
    app.dependency_overrides.clear()
    app.dependency_overrides.update(previous)
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "UNAVAILABLE"


def test_search_fails_open_when_redis_is_unavailable(authenticated_client):
    app.dependency_overrides[get_client] = BrokenRedis
    with patch(
        "app.api.routes_users.user_service.search_users",
        return_value=[{"id": "friend", "name": "Friend", "source": "snap"}],
    ):
        response = authenticated_client.get("/api/v1/users/search?q=fr")
    assert response.status_code == 200


def test_public_profile_requires_auth_and_never_returns_email(authenticated_client):
    public_user = {"id": "friend", "name": "Friend", "source": "app"}
    with patch("app.api.routes_users.user_service.get_user", return_value=public_user):
        response = authenticated_client.get("/api/v1/users/friend")
    assert response.status_code == 200
    assert "email" not in response.json()
    assert "password_hash" not in response.json()


def test_public_profile_remains_available_when_redis_is_down(authenticated_client):
    app.dependency_overrides[get_client] = BrokenRedis
    with patch(
        "app.api.routes_users.user_service.get_user",
        return_value={"id": "friend", "name": "Friend", "source": "snap"},
    ):
        response = authenticated_client.get("/api/v1/users/friend")
    assert response.status_code == 200


def test_search_is_protected_and_uses_public_projection(authenticated_client):
    users = [{"id": "friend", "name": "Friend", "source": "snap"}]
    with patch("app.api.routes_users.user_service.search_users", return_value=users):
        response = authenticated_client.get("/api/v1/users/search?q=fr")
    assert response.status_code == 200
    assert response.json() == users
    assert "email" not in response.text
    assert "password_hash" not in response.text


def test_search_rejects_whitespace_only_query_after_trimming(authenticated_client):
    with patch("app.services.user_service.user_repo.search_users") as search:
        response = authenticated_client.get("/api/v1/users/search?q=%20%20")

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
    search.assert_not_called()


def test_own_profile_can_include_only_own_email(authenticated_client):
    profile = {
        "id": "test-user",
        "name": "Alice",
        "source": "app",
        "email": "alice@example.com",
    }
    with patch(
        "app.api.routes_users.user_service.get_own_profile", return_value=profile
    ):
        response = authenticated_client.get("/api/v1/users/me")
    assert response.status_code == 200
    assert response.json()["email"] == profile["email"]
    assert "password_hash" not in response.text


def test_profile_update_changes_name_only(authenticated_client):
    profile = {
        "id": "test-user",
        "name": "Alicia",
        "source": "app",
        "email": "alice@example.com",
    }
    with (
        patch(
            "app.api.routes_users.user_service.update_own_profile", return_value=profile
        ) as update,
    ):
        response = authenticated_client.put("/api/v1/users/me", json={"name": "Alicia"})
    assert response.status_code == 200
    update.assert_called_once_with(ANY, "test-user", "Alicia")
    assert response.json()["email"] == "alice@example.com"
    rejected = authenticated_client.put(
        "/api/v1/users/me", json={"name": "Alicia", "email": "other@example.com"}
    )
    assert rejected.status_code == 422


def test_protected_user_routes_reject_missing_token():
    for path in (
        "/api/v1/users/me",
        "/api/v1/users/x",
        "/api/v1/users/search?q=ab",
        "/api/v1/path/a/b",
        "/api/v1/suggestions/me",
        "/api/v1/users/a/suggestions",
    ):
        response = client.get(path)
        assert response.status_code == 401
        assert response.json()["error"]["code"] == "UNAUTHENTICATED"


def test_current_user_rejects_token_for_deleted_user(monkeypatch):
    from app.repositories import user_repo

    monkeypatch.setattr(user_repo, "user_exists", lambda *_args: False)
    response = client.get(
        "/api/v1/users/me",
        headers={"Authorization": f"Bearer {create_access_token('deleted-user')}"},
    )
    assert response.status_code == 401


def test_current_user_rejects_non_object_jwt_payload(monkeypatch):
    monkeypatch.setattr("app.api.deps.decode_access_token", lambda _token: [])
    response = client.get(
        "/api/v1/users/me",
        headers={"Authorization": f"Bearer {create_access_token('user')}"},
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHENTICATED"


def test_path_endpoint_returns_named_nodes_from_path_service(authenticated_client):
    path = {
        "start_user": "0",
        "end_user": "150",
        "path": [
            {"id": "0", "name": "User 0"},
            {"id": "107", "name": "User 107"},
            {"id": "150", "name": "User 150"},
        ],
        "hops": 2,
        "cached": False,
    }
    with patch(
        "app.api.routes_graph.path_service.find_path", return_value=path
    ) as find_path:
        response = authenticated_client.get("/api/v1/path/0/150")
    assert response.status_code == 200
    assert response.json()["cached"] is False
    assert response.json()["path"][0] == {"id": "0", "name": "User 0"}
    find_path.assert_called_once_with(ANY, "0", "150", ANY)


@pytest.mark.parametrize(
    ("neo4j_code", "expected_status", "expected_code"),
    [
        ("Neo.ClientError.Transaction.TransactionTimedOut", 504, "UNAVAILABLE"),
        ("Neo.ClientError.Statement.SyntaxError", 500, "INTERNAL"),
    ],
)
def test_path_query_timeout_maps_to_gateway_timeout_only(
    authenticated_client, monkeypatch, neo4j_code, expected_status, expected_code
):
    timeout = Neo4jError._hydrate_neo4j(
        code=neo4j_code, message="database error for test"
    )
    monkeypatch.setattr(
        "app.api.routes_graph.path_service.find_path", Mock(side_effect=timeout)
    )

    response = authenticated_client.get("/api/v1/path/start/end")

    assert isinstance(timeout, Neo4jError)
    if neo4j_code == "Neo.ClientError.Transaction.TransactionTimedOut":
        assert type(timeout).__name__ == "ClientError"
    assert response.status_code == expected_status
    assert response.json()["error"]["code"] == expected_code


def test_suggestions_routes_use_paged_recommendation_service(authenticated_client):
    suggestions = {
        "user_id": "test-user",
        "suggestions": [{"user_id": "friend", "name": "Friend", "mutual_friends": 3}],
        "limit": 5,
        "offset": 2,
    }
    with patch(
        "app.api.routes_graph.recommendation_service.get_suggestions",
        return_value=suggestions,
    ) as get_suggestions:
        response = authenticated_client.get("/api/v1/suggestions/me?limit=5&offset=2")
        other = authenticated_client.get(
            "/api/v1/users/target/suggestions?limit=5&offset=2"
        )
    assert response.status_code == 200
    assert response.json()["suggestions"][0]["name"] == "Friend"
    assert response.json()["limit"] == 5
    assert other.status_code == 200
    assert get_suggestions.call_args_list == [
        call(ANY, "test-user", offset=2, limit=5),
        call(ANY, "target", offset=2, limit=5),
    ]
    assert client.get("/api/v1/suggestions/target").status_code == 404


def test_friend_route_remains_scoped_to_authenticated_caller(authenticated_client):
    with (
        patch.object(
            app.state.friend_service, "add_friend", return_value={"created": True}
        ) as add_friend,
    ):
        response = authenticated_client.post("/api/v1/friends/friend")
    assert response.status_code == 201
    add_friend.assert_called_once_with(ANY, "test-user", "friend")


def test_friend_endpoints_are_versioned_authenticated_and_validate_ids(
    authenticated_client,
):
    with (
        patch.object(
            app.state.friend_service,
            "list_friends",
            return_value=[{"id": "friend", "name": "Friend", "source": "app"}],
        ) as list_friends,
        patch.object(
            app.state.friend_service,
            "remove_friend",
            return_value={"removed": False},
        ) as remove_friend,
        patch.object(app.state.friend_service, "mutual_friends", return_value=[])
        as mutual_friends,
    ):
        friends = authenticated_client.get("/api/v1/friends?limit=1&offset=0")
        removed = authenticated_client.delete("/api/v1/friends/friend")
        mutual = authenticated_client.get("/api/v1/users/friend/mutual")
        malformed = authenticated_client.post("/api/v1/friends/%27")

    assert friends.status_code == 200
    assert friends.json()["items"][0]["id"] == "friend"
    assert removed.json() == {"removed": False}
    assert mutual.json()["items"] == []
    assert malformed.status_code == 422
    assert malformed.json()["error"]["code"] == "VALIDATION_ERROR"
    list_friends.assert_called_once_with(ANY, "test-user", offset=0, limit=1)
    remove_friend.assert_called_once_with(ANY, "test-user", "friend")
    mutual_friends.assert_called_once_with(
        ANY, "test-user", "friend", offset=0, limit=20
    )


def test_unversioned_friend_routes_are_removed():
    for method in (client.get, client.post, client.delete):
        response = method("/friends/someone")
        assert response.status_code == 404
