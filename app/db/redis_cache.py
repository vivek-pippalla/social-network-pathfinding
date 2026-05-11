import json
import logging
import redis
from app.core.config import settings

logger = logging.getLogger(__name__)

# Singleton Redis client
_client: redis.Redis = None


def get_client() -> redis.Redis:
    global _client
    if _client is None:
        _client = redis.from_url(settings.REDIS_URL, decode_responses=True)
    return _client


def get_cached_path(cache_key: str) -> dict | None:
    """
    Retrieve a cached path from Redis.
    Returns the path dict on hit, or None on miss.
    """
    try:
        data = get_client().get(cache_key)
        if data:
            logger.info(f"Cache HIT  | key={cache_key}")
            return json.loads(data)
        logger.info(f"Cache MISS | key={cache_key}")
        return None
    except Exception as e:
        # Redis errors must not crash the API — fall through to Neo4j
        logger.error(f"Redis GET error: {e}")
        return None


def set_cached_path(cache_key: str, value: dict, ttl: int = None) -> None:
    """
    Store a path result in Redis with an expiration (TTL).
    Defaults to CACHE_TTL_SECONDS from config.
    """
    ttl = ttl or settings.CACHE_TTL_SECONDS
    try:
        get_client().setex(cache_key, ttl, json.dumps(value))
        logger.info(f"Cache SET  | key={cache_key} | ttl={ttl}s")
    except Exception as e:
        logger.error(f"Redis SET error: {e}")
