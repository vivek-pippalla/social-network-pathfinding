import logging
from neo4j import Driver
from app.models.schemas import UserCreate
from app.repositories import user_repo
from app.core.exceptions import UserNotFoundException

logger = logging.getLogger(__name__)


def create_user(driver: Driver, user: UserCreate) -> dict:
    created = user_repo.create_user(driver, user)
    logger.info(f"User created: {created['id']} — {created['name']}")
    return created


def get_user(driver: Driver, user_id: str) -> dict:
    user = user_repo.get_user_by_id(driver, user_id)
    if not user:
        raise UserNotFoundException(user_id)
    return user


def search_users(driver: Driver, query: str) -> list[dict]:
    return user_repo.search_users(driver, query)
