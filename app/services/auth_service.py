import logging
import uuid
from datetime import timedelta

from neo4j import Driver
from neo4j.exceptions import ConstraintError
from redis import Redis

from app.core import rate_limit
from app.core.config import settings
from app.core.metrics import AUTH_FAILURES
from app.core.observability import email_identifier
from app.core.security import (
    create_access_token,
    dummy_password_hash,
    hash_password,
    password_needs_rehash,
    verify_password,
)
from app.domain.errors import AppError, EmailTakenError
from app.repositories import account_repo

INVALID_CREDENTIALS = "Incorrect email or password."
logger = logging.getLogger(__name__)


def _token_response(user_id: str) -> dict:
    expires_in = settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    return {
        "access_token": create_access_token(user_id, timedelta(seconds=expires_in)),
        "token_type": "bearer",
        "expires_in": expires_in,
    }


def register(
    driver: Driver,
    redis_client: Redis,
    *,
    client_ip: str,
    name: str,
    email: str,
    password: str,
) -> dict:
    rate_limit.check_registration(redis_client, client_ip)
    normalized_email = email.strip().lower()
    try:
        created = account_repo.create_account_and_user(
            driver,
            user_id=uuid.uuid4().hex,
            name=name,
            email=email.strip(),
            email_normalized=normalized_email,
            password_hash=hash_password(password),
        )
    except ConstraintError as exc:
        if (
            "account_email_unique" in str(exc).lower()
            or "email_normalized" in str(exc).lower()
        ):
            raise EmailTakenError() from None
        raise
    return _token_response(created["id"])


def login(
    driver: Driver,
    redis_client: Redis,
    *,
    client_ip: str,
    email: str,
    password: str,
) -> dict:
    normalized_email = email.strip().lower()
    rate_limit.check_login(redis_client, client_ip, normalized_email)
    account = account_repo.get_account_by_email(driver, normalized_email)
    dummy_hash = dummy_password_hash()
    password_hash = account["password_hash"] if account else dummy_hash
    valid_password = verify_password(password, password_hash)
    if account is None or not valid_password:
        AUTH_FAILURES.labels(operation="login", reason="invalid_credentials").inc()
        logger.warning(
            "login_failed",
            extra={
                "event": "login_failed",
                "operation": "login",
                "email_hash": email_identifier(normalized_email),
            },
        )
        raise AppError("UNAUTHENTICATED", INVALID_CREDENTIALS, 401)
    if password_needs_rehash(account["password_hash"]):
        account_repo.update_password_hash(
            driver, account["user_id"], hash_password(password)
        )
    return _token_response(account["user_id"])


def check_search_limit(redis_client: Redis, client_ip: str) -> None:
    rate_limit.check_search(redis_client, client_ip)
