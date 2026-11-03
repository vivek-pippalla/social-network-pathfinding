from neo4j import Driver
from app.repositories import user_repo
from app.core.exceptions import UserNotFoundException

def get_user(driver: Driver, user_id: str) -> dict:
    user = user_repo.get_user_by_id(driver, user_id)
    if not user:
        raise UserNotFoundException(user_id)
    return user


def update_user(driver: Driver, user_id: str, name: str) -> dict:
    user = user_repo.update_user(driver, user_id, name=name)
    if not user:
        raise UserNotFoundException(user_id)
    return user


def search_users(driver: Driver, query: str) -> list[dict]:
    return user_repo.search_users(driver, query)
