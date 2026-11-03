from neo4j import Driver

from app.domain.errors import AppError
from app.repositories import graph_repo


def get_suggestions(
    driver: Driver, user_id: str, offset: int = 0, limit: int = 20
) -> dict:
    users = graph_repo.get_users_by_ids(driver, [user_id])
    if user_id not in users:
        raise AppError("USER_NOT_FOUND", "User not found.", 404)
    suggestions = graph_repo.get_recommendations(
        driver, user_id, offset=offset, limit=limit
    )
    return {
        "user_id": user_id,
        "suggestions": suggestions,
        "limit": limit,
        "offset": offset,
    }
