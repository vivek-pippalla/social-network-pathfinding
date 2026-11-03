from neo4j import Driver

from app.core.config import settings
from app.domain.errors import AppError
from app.repositories import graph_repo
from app.services.cache_service import CacheService, PathCacheLookup


def _validated_max_depth() -> int:
    try:
        depth = int(settings.MAX_PATH_DEPTH)
    except (TypeError, ValueError):
        raise AppError(
            "INTERNAL", "Pathfinding configuration is invalid.", 500
        ) from None
    if depth < 1:
        raise AppError("INTERNAL", "Pathfinding configuration is invalid.", 500)
    return depth


def find_path(
    driver: Driver,
    start_id: str,
    end_id: str,
    cache: CacheService | None = None,
) -> dict:
    users = graph_repo.get_users_by_ids(driver, [start_id, end_id])
    if start_id not in users or end_id not in users:
        raise AppError("USER_NOT_FOUND", "User not found.", 404)

    if start_id == end_id:
        path = [users[start_id]]
        return _path_response(start_id, end_id, path, cached=False)

    cache_lookup = (
        cache.get_path(start_id, end_id)
        if cache is not None
        else PathCacheLookup(version=None, hit=False)
    )
    if cache_lookup.hit:
        if cache_lookup.path is None:
            raise AppError(
                "PATH_NOT_FOUND", "No path found within the search depth.", 404
            )
        return _path_response(start_id, end_id, cache_lookup.path, cached=True)

    path = graph_repo.find_bounded_shortest_path(
        driver, start_id, end_id, _validated_max_depth()
    )
    if cache is not None:
        cache.set_path(start_id, end_id, path, version=cache_lookup.version)
    if path is None:
        raise AppError("PATH_NOT_FOUND", "No path found within the search depth.", 404)
    return _path_response(start_id, end_id, path, cached=False)


def _path_response(
    start_id: str, end_id: str, path: list[dict], *, cached: bool
) -> dict:
    return {
        "start_user": start_id,
        "end_user": end_id,
        "path": path,
        "hops": len(path) - 1,
        "cached": cached,
    }
