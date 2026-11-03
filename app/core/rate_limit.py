import hashlib
import logging

from redis import Redis

from app.domain.errors import RateLimitedError, UnavailableError

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


def _increment(redis_client: Redis, key: str, limit: int) -> int:
    count, ttl = redis_client.eval(_INCREMENT_WITH_WINDOW, 1, key, WINDOW_SECONDS)
    if int(count) > limit:
        raise RateLimitedError(max(1, int(ttl)))
    return int(count)


def check_login(redis_client: Redis, client_ip: str, normalized_email: str) -> None:
    email_digest = hashlib.sha256(normalized_email.encode("utf-8")).hexdigest()
    try:
        _increment(redis_client, f"rate:login:ip:{client_ip}", LOGIN_IP_LIMIT)
        _increment(
            redis_client,
            f"rate:login:email:{client_ip}:{email_digest}",
            LOGIN_EMAIL_LIMIT,
        )
    except RateLimitedError:
        raise
    except Exception:
        logger.warning("rate_limit_unavailable", extra={"operation": "login"})
        raise UnavailableError("redis") from None


def check_registration(redis_client: Redis, client_ip: str) -> None:
    try:
        _increment(redis_client, f"rate:register:ip:{client_ip}", REGISTER_IP_LIMIT)
    except RateLimitedError:
        raise
    except Exception:
        logger.warning("rate_limit_unavailable", extra={"operation": "register"})
        raise UnavailableError("redis") from None


def check_search(redis_client: Redis, client_ip: str) -> None:
    try:
        _increment(redis_client, f"rate:search:ip:{client_ip}", SEARCH_IP_LIMIT)
    except RateLimitedError:
        raise
    except Exception:
        logger.warning("rate_limit_unavailable", extra={"operation": "search"})
