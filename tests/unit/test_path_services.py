from unittest.mock import Mock

import pytest

from app.core.config import settings
from app.domain.errors import AppError
from app.repositories import graph_repo
from app.services.cache_service import PathCacheLookup
from app.services import path_service, recommendation_service
from tests.support.oracle import bfs_shortest_path


def test_bfs_oracle_handles_shortest_disconnected_and_depth_bounded_cases():
    graph = {
        "a": {"b", "c"},
        "b": {"a", "d"},
        "c": {"a", "d"},
        "d": {"b", "c"},
        "island": set(),
    }

    assert bfs_shortest_path(graph, "a", "d") == ["a", "b", "d"]
    assert bfs_shortest_path(graph, "a", "d", max_depth=1) is None
    assert bfs_shortest_path(graph, "a", "a") == ["a"]
    assert bfs_shortest_path(graph, "a", "island") is None
    assert bfs_shortest_path(graph, "missing", "a") is None


def test_repository_interpolates_only_validated_integer_depth():
    captured = {}

    class Result:
        def single(self):
            return {"path": [{"id": "a", "name": "A"}]}

    class Transaction:
        def run(self, query, **parameters):
            captured["query"] = query
            captured["parameters"] = parameters
            return Result()

    class Session:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def execute_read(self, callback):
            captured["callback"] = callback
            return callback(Transaction())

    class Driver:
        def session(self):
            return Session()

    assert graph_repo.find_bounded_shortest_path(Driver(), "a", "a", 7) == [
        {"id": "a", "name": "A"}
    ]
    query_text = (
        captured["query"].text
        if hasattr(captured["query"], "text")
        else captured["query"]
    )
    assert "CONNECTED*..7" in query_text
    assert captured["parameters"] == {"start_id": "a", "end_id": "a"}
    timeout = getattr(
        captured["query"],
        "timeout",
        getattr(captured.get("callback"), "timeout", None),
    )
    assert timeout == settings.NEO4J_QUERY_TIMEOUT_SECONDS


@pytest.mark.parametrize("depth", [True, 0, -1, "2; MATCH (n) DETACH DELETE n"])
def test_repository_rejects_invalid_depth_before_opening_driver(depth):
    class DriverShouldNotBeUsed:
        def session(self):
            pytest.fail("invalid depth must be rejected before opening a session")

    with pytest.raises(ValueError):
        graph_repo.find_bounded_shortest_path(DriverShouldNotBeUsed(), "a", "b", depth)


def test_same_user_path_returns_one_node_without_path_query(monkeypatch):
    user = {"same": {"id": "same", "name": "Same"}}
    monkeypatch.setattr(
        path_service.graph_repo, "get_users_by_ids", Mock(return_value=user)
    )
    find_path = Mock()
    monkeypatch.setattr(
        path_service.graph_repo, "find_bounded_shortest_path", find_path
    )

    result = path_service.find_path(object(), "same", "same")

    assert result == {
        "start_user": "same",
        "end_user": "same",
        "path": [{"id": "same", "name": "Same"}],
        "hops": 0,
        "cached": False,
    }
    find_path.assert_not_called()


def test_path_checks_both_users_before_running_search(monkeypatch):
    get_users = Mock(return_value={"a": {"id": "a", "name": "A"}})
    monkeypatch.setattr(path_service.graph_repo, "get_users_by_ids", get_users)
    find_path = Mock()
    monkeypatch.setattr(
        path_service.graph_repo, "find_bounded_shortest_path", find_path
    )

    driver = object()
    with pytest.raises(AppError) as error:
        path_service.find_path(driver, "a", "missing")

    assert (error.value.code, error.value.status) == ("USER_NOT_FOUND", 404)
    get_users.assert_called_once_with(driver, ["a", "missing"])
    find_path.assert_not_called()


def test_bounded_path_uses_validated_configured_depth(monkeypatch):
    monkeypatch.setattr(path_service.settings, "MAX_PATH_DEPTH", "4")
    monkeypatch.setattr(
        path_service.graph_repo,
        "get_users_by_ids",
        Mock(return_value={"a": {"id": "a"}, "b": {"id": "b"}}),
    )
    find_path = Mock(return_value=[{"id": "a", "name": "A"}, {"id": "b", "name": "B"}])
    monkeypatch.setattr(
        path_service.graph_repo, "find_bounded_shortest_path", find_path
    )

    result = path_service.find_path(object(), "a", "b")

    assert result["hops"] == 1
    assert result["cached"] is False
    assert find_path.call_args.args[3] == 4


def test_invalid_depth_config_is_rejected_before_path_query(monkeypatch):
    monkeypatch.setattr(path_service.settings, "MAX_PATH_DEPTH", "2]-(x)")
    monkeypatch.setattr(
        path_service.graph_repo,
        "get_users_by_ids",
        Mock(return_value={"a": {"id": "a"}, "b": {"id": "b"}}),
    )
    find_path = Mock()
    monkeypatch.setattr(
        path_service.graph_repo, "find_bounded_shortest_path", find_path
    )

    with pytest.raises(AppError) as error:
        path_service.find_path(object(), "a", "b")

    assert error.value.code == "INTERNAL"
    find_path.assert_not_called()


def test_no_path_within_bound_uses_path_not_found_code(monkeypatch):
    monkeypatch.setattr(
        path_service.graph_repo,
        "get_users_by_ids",
        Mock(return_value={"a": {"id": "a"}, "b": {"id": "b"}}),
    )
    monkeypatch.setattr(
        path_service.graph_repo, "find_bounded_shortest_path", Mock(return_value=None)
    )

    with pytest.raises(AppError) as error:
        path_service.find_path(object(), "a", "b")

    assert (error.value.code, error.value.status) == ("PATH_NOT_FOUND", 404)


def test_path_cache_hit_is_oriented_and_skips_path_query(monkeypatch):
    users = {
        "a": {"id": "a", "name": "A"},
        "c": {"id": "c", "name": "C"},
    }
    monkeypatch.setattr(
        path_service.graph_repo, "get_users_by_ids", Mock(return_value=users)
    )
    query = Mock()
    monkeypatch.setattr(path_service.graph_repo, "find_bounded_shortest_path", query)
    cache = Mock()
    cache.get_path.return_value = PathCacheLookup(
        version=3,
        hit=True,
        path=[
            {"id": "c", "name": "C"},
            {"id": "b", "name": "B"},
            {"id": "a", "name": "A"},
        ],
    )

    result = path_service.find_path(object(), "c", "a", cache)

    assert result["cached"] is True
    assert [node["id"] for node in result["path"]] == ["c", "b", "a"]
    assert (result["start_user"], result["end_user"], result["hops"]) == (
        "c",
        "a",
        2,
    )
    cache.get_path.assert_called_once_with("c", "a")
    query.assert_not_called()


def test_negative_cache_hit_returns_path_not_found_without_path_query(monkeypatch):
    monkeypatch.setattr(
        path_service.graph_repo,
        "get_users_by_ids",
        Mock(return_value={"a": {"id": "a"}, "z": {"id": "z"}}),
    )
    query = Mock()
    monkeypatch.setattr(path_service.graph_repo, "find_bounded_shortest_path", query)
    cache = Mock()
    cache.get_path.return_value = PathCacheLookup(version=0, hit=True, path=None)

    with pytest.raises(AppError) as error:
        path_service.find_path(object(), "a", "z", cache)

    assert (error.value.code, error.value.status) == ("PATH_NOT_FOUND", 404)
    query.assert_not_called()


def test_path_miss_stores_positive_result_under_observed_version(monkeypatch):
    driver = object()
    result_path = [{"id": "a", "name": "A"}, {"id": "b", "name": "B"}]
    monkeypatch.setattr(
        path_service.graph_repo,
        "get_users_by_ids",
        Mock(return_value={"a": result_path[0], "b": result_path[1]}),
    )
    monkeypatch.setattr(
        path_service.graph_repo,
        "find_bounded_shortest_path",
        Mock(return_value=result_path),
    )
    cache = Mock()
    cache.get_path.return_value = PathCacheLookup(version=9, hit=False)

    response = path_service.find_path(driver, "a", "b", cache)

    assert response["cached"] is False
    cache.set_path.assert_called_once_with("a", "b", result_path, version=9)


def test_path_query_failure_is_not_cached(monkeypatch):
    monkeypatch.setattr(
        path_service.graph_repo,
        "get_users_by_ids",
        Mock(return_value={"a": {"id": "a"}, "b": {"id": "b"}}),
    )
    query_error = RuntimeError("database query failed")
    monkeypatch.setattr(
        path_service.graph_repo,
        "find_bounded_shortest_path",
        Mock(side_effect=query_error),
    )
    cache = Mock()
    cache.get_path.return_value = PathCacheLookup(version=4, hit=False)

    with pytest.raises(RuntimeError, match="database query failed"):
        path_service.find_path(object(), "a", "b", cache)

    cache.set_path.assert_not_called()


def test_unknown_users_are_rejected_before_consulting_path_cache(monkeypatch):
    monkeypatch.setattr(
        path_service.graph_repo,
        "get_users_by_ids",
        Mock(return_value={"a": {"id": "a"}}),
    )
    cache = Mock()

    with pytest.raises(AppError) as error:
        path_service.find_path(object(), "a", "missing", cache)

    assert error.value.code == "USER_NOT_FOUND"
    cache.get_path.assert_not_called()


def test_recommendations_check_user_before_query_and_include_paging(monkeypatch):
    graph_repo = recommendation_service.graph_repo
    get_users = Mock(return_value={})
    monkeypatch.setattr(graph_repo, "get_users_by_ids", get_users)
    query = Mock()
    monkeypatch.setattr(graph_repo, "get_recommendations", query)

    driver = object()
    with pytest.raises(AppError) as error:
        recommendation_service.get_suggestions(driver, "unknown", offset=4, limit=3)
    assert (error.value.code, error.value.status) == ("USER_NOT_FOUND", 404)
    query.assert_not_called()

    get_users.return_value = {"known": {"id": "known"}}
    query.return_value = [
        {"user_id": "candidate", "name": "Candidate", "mutual_friends": 2}
    ]
    result = recommendation_service.get_suggestions(driver, "known", offset=4, limit=3)
    assert result == {
        "user_id": "known",
        "suggestions": query.return_value,
        "limit": 3,
        "offset": 4,
    }
    query.assert_called_once_with(driver, "known", offset=4, limit=3)
