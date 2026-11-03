import hashlib
import logging

from redis import Redis

from app.domain.errors import RateLimitedError, UnavailableError
from app.core.metrics import RATE_LIMIT_REJECTIONS

logger = logging.getLogger(__name__)

WINDOW_SECONDS = 60
LOGIN_IP_LIMIT = 5
LOGIN_EMAIL_LIMIT = 5
REGISTER_IP_LIMIT = 5
SEARCH_IP_LIMIT = 30

_INCREMENT_WITH_WINDOW = """
local value = redis.call('INCR', KEYS[1])
if value == 1 then redis.call('EXPIRE', KEYS[1], ARGV[1]) end
return {value, redis.call('TTL', KEYS[1])}
"""


def _increment(redis_client: Redis, key: str, limit: int, operation: str) -> int:
    count, ttl = redis_client.eval(_INCREMENT_WITH_WINDOW, 1, key, WINDOW_SECONDS)
    if int(count) > limit:
        RATE_LIMIT_REJECTIONS.labels(operation=operation).inc()
        logger.warning(
            "rate_limit_rejected",
            extra={"event": "rate_limit_rejected", "operation": operation},
        )
        raise RateLimitedError(max(1, int(ttl)))
    return int(count)


def check_login(redis_client: Redis, client_ip: str, normalized_email: str) -> None:
    email_digest = hashlib.sha256(normalized_email.encode("utf-8")).hexdigest()
    try:
        _increment(
            redis_client,
            f"rate:login:ip:{client_ip}",
            LOGIN_IP_LIMIT,
            "login",
        )
        _increment(
            redis_client,
            f"rate:login:email:{client_ip}:{email_digest}",
            LOGIN_EMAIL_LIMIT,
            "login",
        )
    except RateLimitedError:
        raise
    except Exception:
        logger.warning(
            "rate_limit_unavailable",
            extra={"event": "rate_limit_unavailable", "operation": "login"},
        )
        raise UnavailableError("redis") from None


def check_registration(redis_client: Redis, client_ip: str) -> None:
    try:
        _increment(
            redis_client,
            f"rate:register:ip:{client_ip}",
            REGISTER_IP_LIMIT,
            "register",
        )
    except RateLimitedError:
        raise
    except Exception:
        logger.warning(
            "rate_limit_unavailable",
            extra={"event": "rate_limit_unavailable", "operation": "register"},
        )
        raise UnavailableError("redis") from None


def check_search(redis_client: Redis, client_ip: str) -> None:
    try:
        _increment(
            redis_client,
            f"rate:search:ip:{client_ip}",
            SEARCH_IP_LIMIT,
            "search",
        )
    except RateLimitedError:
        raise
    except Exception:
        logger.warning(
            "rate_limit_unavailable",
            extra={"event": "rate_limit_unavailable", "operation": "search"},
        )
