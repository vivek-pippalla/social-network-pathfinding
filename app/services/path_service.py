from neo4j import Driver

from app.core.config import settings
from app.domain.errors import AppError
from app.repositories import graph_repo


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


def find_path(driver: Driver, start_id: str, end_id: str) -> dict:
    users = graph_repo.get_users_by_ids(driver, [start_id, end_id])
    if start_id not in users or end_id not in users:
        raise AppError("USER_NOT_FOUND", "User not found.", 404)

    if start_id == end_id:
        path = [users[start_id]]
    else:
        path = graph_repo.find_bounded_shortest_path(
            driver, start_id, end_id, _validated_max_depth()
        )
        if path is None:
            raise AppError(
                "PATH_NOT_FOUND", "No path found within the search depth.", 404
            )

    return {
        "start_user": start_id,
        "end_user": end_id,
        "path": path,
        "hops": len(path) - 1,
        "cached": False,
    }
