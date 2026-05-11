import logging
import time
from neo4j import Driver
from app.repositories import graph_repo
from app.db import redis_cache
from app.core.exceptions import PathNotFoundException
from app.models.schemas import SuggestedUser

logger = logging.getLogger(__name__)


def find_shortest_path(driver: Driver, start_id: str, end_id: str) -> dict:
    """
    Core pathfinding logic.
    Flow: Redis Cache → Neo4j shortestPath → Cache result → Return

    The cache key is order-independent so path:A:B and path:B:A hit the same entry.
    """
    # Build a stable, order-independent cache key
    cache_key = f"path:{min(start_id, end_id)}:{max(start_id, end_id)}"

    # 1. Check Redis cache
    cached_result = redis_cache.get_cached_path(cache_key)
    if cached_result:
        cached_result["cached"] = True
        return cached_result

    # 2. Cache miss — query Neo4j
    logger.info(f"Querying Neo4j | {start_id} → {end_id}")
    t_start = time.perf_counter()
    path = graph_repo.find_shortest_path(driver, start_id, end_id)
    latency_ms = round((time.perf_counter() - t_start) * 1000, 2)
    logger.info(f"Neo4j query completed | latency={latency_ms}ms")

    if not path:
        raise PathNotFoundException(start_id, end_id)

    result = {
        "start_user": start_id,
        "end_user": end_id,
        "path": path,
        "hops": len(path) - 1,
        "cached": False,
    }

    # 3. Store in Redis for future requests
    redis_cache.set_cached_path(cache_key, result)

    return result


def get_suggestions(driver: Driver, user_id: str) -> dict:
    """Return friend-of-friend suggestions ranked by mutual friend count."""
    raw = graph_repo.get_friend_suggestions(driver, user_id)
    suggestions = [
        SuggestedUser(user_id=suggested, mutual_friends=count)
        for suggested, count in raw
    ]
    return {"user_id": user_id, "suggestions": suggestions}
