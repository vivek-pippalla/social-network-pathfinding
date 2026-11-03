from collections.abc import Callable

from neo4j import Driver

from app.core.exceptions import UserNotFoundException
from app.domain.errors import AppError
from app.repositories import graph_repo, user_repo

GraphChangedHook = Callable[[], None]


def _noop_graph_changed() -> None:
    return None


class FriendService:
    def __init__(self, on_graph_changed: GraphChangedHook = _noop_graph_changed):
        self._on_graph_changed = on_graph_changed

    def add_friend(self, driver: Driver, caller_id: str, friend_id: str) -> dict:
        if caller_id == friend_id:
            raise AppError("CANNOT_FRIEND_SELF", "You cannot friend yourself.", 400)
        exists, changed = graph_repo.add_friendship(driver, caller_id, friend_id)
        if not exists:
            raise UserNotFoundException(friend_id)
        if changed:
            self._on_graph_changed()
        return {"created": changed}

    def remove_friend(self, driver: Driver, caller_id: str, friend_id: str) -> dict:
        if caller_id == friend_id:
            raise AppError("CANNOT_FRIEND_SELF", "You cannot friend yourself.", 400)
        exists, changed = graph_repo.remove_friendship(driver, caller_id, friend_id)
        if not exists:
            raise UserNotFoundException(friend_id)
        if changed:
            self._on_graph_changed()
        return {"removed": changed}

    def list_friends(
        self, driver: Driver, caller_id: str, offset: int = 0, limit: int = 20
    ) -> list[dict]:
        if not user_repo.user_exists(driver, caller_id):
            raise UserNotFoundException(caller_id)
        return graph_repo.list_friends(driver, caller_id, offset=offset, limit=limit)

    def mutual_friends(
        self,
        driver: Driver,
        caller_id: str,
        other_id: str,
        offset: int = 0,
        limit: int = 20,
    ) -> list[dict]:
        if not user_repo.user_exists(driver, other_id):
            raise UserNotFoundException(other_id)
        return graph_repo.mutual_friends(
            driver, caller_id, other_id, offset=offset, limit=limit
        )


friend_service = FriendService()
