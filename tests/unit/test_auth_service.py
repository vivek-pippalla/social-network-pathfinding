from unittest.mock import MagicMock

import pytest

from app.domain.errors import (
    AppError,
    EmailTakenError,
    RateLimitedError,
    UnavailableError,
)
from app.services import auth_service


def test_unknown_login_uses_dummy_hash_and_returns_same_auth_error(monkeypatch):
    driver = object()
    redis = object()
    dummy_verify = MagicMock(return_value=False)
    monkeypatch.setattr(auth_service.rate_limit, "check_login", lambda *_args: None)
    monkeypatch.setattr(
        auth_service.account_repo, "get_account_by_email", lambda *_a: None
    )
    monkeypatch.setattr(auth_service, "dummy_password_hash", lambda: "dummy-hash")
    monkeypatch.setattr(auth_service, "verify_password", dummy_verify)

    with pytest.raises(AppError) as error:
        auth_service.login(
            driver,
            redis,
            client_ip="127.0.0.1",
            email="unknown@example.com",
            password="incorrect",
        )
    dummy_verify.assert_called_once_with("incorrect", "dummy-hash")
    assert (error.value.status, error.value.code, error.value.message) == (
        401,
        "UNAUTHENTICATED",
        auth_service.INVALID_CREDENTIALS,
    )


def test_wrong_password_uses_same_error_as_unknown_account(monkeypatch):
    monkeypatch.setattr(auth_service.rate_limit, "check_login", lambda *_args: None)
    monkeypatch.setattr(
        auth_service.account_repo,
        "get_account_by_email",
        lambda *_args: {"user_id": "u", "password_hash": "hash"},
    )
    monkeypatch.setattr(auth_service, "verify_password", lambda *_args: False)
    monkeypatch.setattr(auth_service, "dummy_password_hash", lambda: "dummy")

    with pytest.raises(AppError) as error:
        auth_service.login(
            object(),
            object(),
            client_ip="127.0.0.1",
            email="known@example.com",
            password="incorrect",
        )
    assert error.value.message == auth_service.INVALID_CREDENTIALS
    assert error.value.status == 401


def test_dummy_hash_is_initialized_on_first_login_even_for_known_account(monkeypatch):
    dummy = MagicMock(return_value="dummy-hash")
    monkeypatch.setattr(auth_service.rate_limit, "check_login", lambda *_args: None)
    monkeypatch.setattr(
        auth_service.account_repo,
        "get_account_by_email",
        lambda *_args: {"user_id": "u", "password_hash": "stored-hash"},
    )
    monkeypatch.setattr(auth_service, "dummy_password_hash", dummy)
    monkeypatch.setattr(auth_service, "verify_password", lambda *_args: False)
    with pytest.raises(AppError):
        auth_service.login(
            object(),
            object(),
            client_ip="127.0.0.1",
            email="known@example.com",
            password="incorrect",
        )
    dummy.assert_called_once_with()


def test_registration_normalizes_email_and_uses_full_uuid(monkeypatch):
    captured = {}
    monkeypatch.setattr(
        auth_service.rate_limit, "check_registration", lambda *_args: None
    )

    def create(_driver, **values):
        captured.update(values)
        return {"id": values["user_id"]}

    monkeypatch.setattr(auth_service.account_repo, "create_account_and_user", create)
    monkeypatch.setattr(auth_service, "hash_password", lambda value: f"hashed:{value}")
    monkeypatch.setattr(
        auth_service, "create_access_token", lambda user_id, _ttl: user_id
    )
    result = auth_service.register(
        object(),
        object(),
        client_ip="127.0.0.1",
        name="Alice",
        email=" Alice@Example.com ",
        password="a-valid-long-password",
    )
    assert len(captured["user_id"]) == 32
    assert captured["email"] == "Alice@Example.com"
    assert captured["email_normalized"] == "alice@example.com"
    assert captured["password_hash"] == "hashed:a-valid-long-password"
    assert result["expires_in"] == 1800


def test_registration_maps_only_email_constraint(monkeypatch):
    from neo4j.exceptions import ConstraintError

    monkeypatch.setattr(
        auth_service.rate_limit, "check_registration", lambda *_args: None
    )
    monkeypatch.setattr(auth_service, "hash_password", lambda _password: "hash")
    monkeypatch.setattr(
        auth_service.account_repo,
        "create_account_and_user",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            ConstraintError("account_email_unique")
        ),
    )
    with pytest.raises(EmailTakenError):
        auth_service.register(
            object(),
            object(),
            client_ip="127.0.0.1",
            name="Alice",
            email="alice@example.com",
            password="a-valid-long-password",
        )

    monkeypatch.setattr(
        auth_service.account_repo,
        "create_account_and_user",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            ConstraintError("other constraint")
        ),
    )
    with pytest.raises(ConstraintError):
        auth_service.register(
            object(),
            object(),
            client_ip="127.0.0.1",
            name="Alice",
            email="alice@example.com",
            password="a-valid-long-password",
        )


@pytest.mark.parametrize(
    "error,expected_status,expected_header",
    [
        (RateLimitedError(20), 429, ("Retry-After", "20")),
        (UnavailableError("redis"), 503, None),
    ],
)
def test_registration_rate_limit_and_redis_failure_propagate(
    monkeypatch, error, expected_status, expected_header
):
    monkeypatch.setattr(
        auth_service.rate_limit,
        "check_registration",
        lambda *_args: (_ for _ in ()).throw(error),
    )
    with pytest.raises(type(error)) as raised:
        auth_service.register(
            object(),
            object(),
            client_ip="127.0.0.1",
            name="Alice",
            email="alice@example.com",
            password="a-valid-long-password",
        )
    assert raised.value.status == expected_status
    if expected_header:
        assert raised.value.headers[expected_header[0]] == expected_header[1]
