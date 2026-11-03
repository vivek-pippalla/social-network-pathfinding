from unittest.mock import Mock

import pytest

from app.domain.errors import AppError
from app.services.friend_service import FriendService


def test_add_calls_graph_change_hook_only_when_created(monkeypatch):
    hook = Mock()
    service = FriendService(on_graph_changed=hook)
    add = Mock(side_effect=[(True, True), (True, False)])
    monkeypatch.setattr("app.services.friend_service.graph_repo.add_friendship", add)

    assert service.add_friend(object(), "a", "b") == {"created": True}
    assert service.add_friend(object(), "a", "b") == {"created": False}
    hook.assert_called_once_with()


def test_remove_calls_graph_change_hook_only_when_removed(monkeypatch):
    hook = Mock()
    service = FriendService(on_graph_changed=hook)
    remove = Mock(side_effect=[(True, True), (True, False)])
    monkeypatch.setattr(
        "app.services.friend_service.graph_repo.remove_friendship", remove
    )

    assert service.remove_friend(object(), "a", "b") == {"removed": True}
    assert service.remove_friend(object(), "a", "b") == {"removed": False}
    hook.assert_called_once_with()


@pytest.mark.parametrize("operation", ["add_friend", "remove_friend"])
def test_self_friendship_is_rejected_before_repository_call(monkeypatch, operation):
    repo_call = Mock()
    monkeypatch.setattr(
        f"app.services.friend_service.graph_repo.{('add_friendship' if operation == 'add_friend' else 'remove_friendship')}",
        repo_call,
    )
    service = FriendService()

    with pytest.raises(AppError) as caught:
        getattr(service, operation)(object(), "same", "same")

    assert caught.value.code == "CANNOT_FRIEND_SELF"
    assert caught.value.status == 400
    repo_call.assert_not_called()


def test_canonical_pair_orders_ids_lexically():
    from app.repositories.graph_repo import canonical_pair

    assert canonical_pair("z", "a") == ("a", "z")
    assert canonical_pair("a", "z") == ("a", "z")
