from datetime import datetime, timedelta, timezone
from functools import lru_cache

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

from app.core.config import settings

JWT_ALGORITHM = "HS256"
password_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    return password_hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return password_hasher.verify(password_hash, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def password_needs_rehash(password_hash: str) -> bool:
    try:
        return password_hasher.check_needs_rehash(password_hash)
    except (VerificationError, InvalidHashError):
        return True


def create_access_token(user_id: str, expires_delta: timedelta | None = None) -> str:
    issued_at = datetime.now(timezone.utc)
    expires_at = issued_at + (
        expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    return jwt.encode(
        {"sub": user_id, "iat": issued_at, "exp": expires_at},
        settings.SECRET_KEY,
        algorithm=JWT_ALGORITHM,
    )


def decode_access_token(token: str) -> dict:
    return jwt.decode(
        token,
        settings.SECRET_KEY,
        algorithms=[JWT_ALGORITHM],
        options={"require": ["exp", "iat", "sub"]},
    )


@lru_cache(maxsize=1)
def dummy_password_hash() -> str:
    return hash_password("not-a-valid-user-password-for-login-timing")
