from datetime import timedelta

import jwt
import pytest
from pydantic import ValidationError

from app.core.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    password_needs_rehash,
    verify_password,
)
from app.models.schemas import UserRegister


def test_argon2_hash_round_trip_and_rehash_check():
    hashed = hash_password("a-long-enough-secret")
    assert hashed.startswith("$argon2id$")
    assert verify_password("a-long-enough-secret", hashed)
    assert not verify_password("wrong", hashed)
    assert password_needs_rehash(hashed) is False


def test_jwt_contains_required_claims_and_is_timezone_aware():
    claims = decode_access_token(create_access_token("user-123"))
    assert claims["sub"] == "user-123"
    assert 1799 <= claims["exp"] - claims["iat"] <= 1800


@pytest.mark.parametrize(
    "token",
    [
        lambda: create_access_token("u", timedelta(seconds=-1)),
        lambda: jwt.encode(
            {"sub": "u", "iat": 1, "exp": 9999999999}, "", algorithm="none"
        ),
        lambda: jwt.encode(
            {"sub": "u", "iat": 1, "exp": 9999999999},
            "wrong-secret-value-that-is-long-enough-to-avoid-hmac-warnings",
            algorithm="HS256",
        ),
        lambda: jwt.encode(
            {"sub": "u", "iat": 1, "exp": 9999999999},
            "test-only-secret-key-32-bytes-minimum-extra-secret-material",
            algorithm="HS384",
        ),
        lambda: jwt.encode(
            {"sub": "u", "iat": 1},
            "test-only-secret-key-32-bytes-minimum",
            algorithm="HS256",
        ),
        lambda: jwt.encode(
            {"sub": "u", "exp": 9999999999},
            "test-only-secret-key-32-bytes-minimum",
            algorithm="HS256",
        ),
        lambda: jwt.encode(
            {"iat": 1, "exp": 9999999999},
            "test-only-secret-key-32-bytes-minimum",
            algorithm="HS256",
        ),
    ],
)
def test_jwt_rejects_invalid_token_cases(token):
    with pytest.raises(jwt.InvalidTokenError):
        decode_access_token(token())


@pytest.mark.parametrize(
    "payload",
    [
        {"name": "Alice", "email": "not-an-email", "password": "long-password"},
        {"name": "Alice", "email": "alice@example.com", "password": "short"},
        {"name": "Alice", "email": "alice@example.com", "password": "x" * 129},
        {"name": "   ", "email": "alice@example.com", "password": "long-password"},
        {
            "name": "Alice",
            "email": "alice@example.com",
            "password": "alice@example.com",
        },
        {"name": "Alice", "email": "alice@example.com", "password": "Alice"},
    ],
)
def test_registration_validation_rejects_invalid_values(payload):
    with pytest.raises(ValidationError):
        UserRegister.model_validate(payload)


def test_registration_trims_name_and_public_model_has_no_private_fields():
    user = UserRegister.model_validate(
        {"name": " Alice ", "email": "alice@example.com", "password": "long-password"}
    )
    assert user.name == "Alice"
    from app.models.schemas import OwnProfileResponse, PublicUserResponse

    assert set(PublicUserResponse.model_fields) == {"id", "name", "source"}
    assert "email" not in PublicUserResponse.model_fields
    assert set(OwnProfileResponse.model_fields) == {"id", "name", "source", "email"}
