import redis
from app.core.config import settings

# Singleton Redis client
_client: redis.Redis = None


def get_client() -> redis.Redis:
    global _client
    if _client is None:
        _client = redis.from_url(
            settings.REDIS_URL,
            decode_responses=True,
            socket_timeout=settings.REDIS_SOCKET_TIMEOUT_SECONDS,
            socket_connect_timeout=settings.REDIS_SOCKET_TIMEOUT_SECONDS,
        )
    return _client
