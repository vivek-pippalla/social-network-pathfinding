from neo4j import Driver

from app.core.exceptions import UserNotFoundException
from app.domain.errors import AppError
from app.repositories import user_repo


def get_user(driver: Driver, user_id: str) -> dict:
    user = user_repo.get_user_by_id(driver, user_id)
    if not user:
        raise UserNotFoundException(user_id)
    return user


def get_own_profile(driver: Driver, user_id: str) -> dict:
    profile = user_repo.get_own_profile(driver, user_id)
    if not profile:
        raise UserNotFoundException(user_id)
    return profile


def update_user(driver: Driver, user_id: str, name: str) -> dict:
    user = user_repo.update_user(driver, user_id, name=name)
    if not user:
        raise UserNotFoundException(user_id)
    return user


def update_own_profile(driver: Driver, user_id: str, name: str) -> dict:
    update_user(driver, user_id, name)
    return get_own_profile(driver, user_id)


def search_users(
    driver: Driver, query: str, offset: int = 0, limit: int = 20
) -> list[dict]:
    normalized_query = query.strip()
    if not normalized_query:
        raise AppError("VALIDATION_ERROR", "Search query must not be empty.", 422)
    return user_repo.search_users(
        driver, normalized_query, offset=offset, limit=limit
    )
