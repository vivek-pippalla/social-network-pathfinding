import random

import pytest

from app.core.config import settings
from app.domain.errors import AppError
from app.services import path_service, recommendation_service
from tests.support.oracle import bfs_shortest_path

pytestmark = pytest.mark.integration


def _replace_graph(driver, user_ids: list[str], edges: list[tuple[str, str]]) -> None:
    def write_graph(tx):
        tx.run("MATCH (n) DETACH DELETE n").consume()
        tx.run(
            """
            UNWIND $users AS row
            CREATE (:User {id: row.id, name: row.name, source: 'snap'})
            """,
            users=[{"id": user_id, "name": f"User {user_id}"} for user_id in user_ids],
        ).consume()
        tx.run(
            """
            UNWIND $edges AS edge
            MATCH (a:User {id: edge[0]}), (b:User {id: edge[1]})
            CREATE (a)-[:CONNECTED]->(b)
            """,
            edges=[list(edge) for edge in edges],
        ).consume()

    with driver.session() as session:
        session.execute_write(write_graph)


def test_two_hundred_seeded_random_graphs_match_bfs_oracle(clean_graph):
    driver, _ = clean_graph
    rng = random.Random(20261103)
    max_depth = int(settings.MAX_PATH_DEPTH)

    for _ in range(200):
        size = rng.randint(2, 10)
        user_ids = [str(index) for index in range(size)]
        adjacency = {user_id: set() for user_id in user_ids}
        edges = []
        density = rng.uniform(0.08, 0.65)
        for left_index, left in enumerate(user_ids):
            for right in user_ids[left_index + 1 :]:
                if rng.random() < density:
                    edges.append((left, right))
                    adjacency[left].add(right)
                    adjacency[right].add(left)
        _replace_graph(driver, user_ids, edges)

        start, end = rng.choice(user_ids), rng.choice(user_ids)
        expected = bfs_shortest_path(adjacency, start, end, max_depth=max_depth)
        if expected is None:
            with pytest.raises(AppError) as error:
                path_service.find_path(driver, start, end)
            assert (error.value.code, error.value.status) == ("PATH_NOT_FOUND", 404)
            continue

        actual = path_service.find_path(driver, start, end)
        actual_ids = [node["id"] for node in actual["path"]]
        assert actual["hops"] == len(expected) - 1
        assert len(actual_ids) - 1 == len(expected) - 1
        assert actual_ids[0] == start and actual_ids[-1] == end
        assert actual["cached"] is False
        for left, right in zip(actual_ids, actual_ids[1:]):
            assert right in adjacency[left]


def test_unknown_users_same_user_and_depth_bound(clean_graph, monkeypatch):
    driver, _ = clean_graph
    _replace_graph(driver, ["a", "b", "c", "d"], [("a", "b"), ("b", "c"), ("c", "d")])

    same = path_service.find_path(driver, "b", "b")
    assert same["path"] == [{"id": "b", "name": "User b"}]
    assert same["hops"] == 0
    assert same["cached"] is False

    with pytest.raises(AppError) as unknown:
        path_service.find_path(driver, "a", "missing")
    assert (unknown.value.code, unknown.value.status) == ("USER_NOT_FOUND", 404)

    monkeypatch.setattr(settings, "MAX_PATH_DEPTH", 2)
    with pytest.raises(AppError) as too_deep:
        path_service.find_path(driver, "a", "d")
    assert (too_deep.value.code, too_deep.value.status) == ("PATH_NOT_FOUND", 404)


def test_suggestions_are_named_distinct_stable_exclude_friends_and_page(clean_graph):
    driver, _ = clean_graph
    _replace_graph(
        driver,
        ["u", "f1", "f2", "candidate", "later", "existing"],
        [
            ("u", "f1"),
            ("u", "f2"),
            ("f1", "candidate"),
            ("f2", "candidate"),
            ("f1", "later"),
            ("u", "existing"),
            ("f1", "existing"),
        ],
    )
    with driver.session() as session:
        session.run(
            """
            MATCH (a:User {id: 'f1'}), (b:User {id: 'candidate'})
            CREATE (a)-[:CONNECTED]->(b)
            """
        ).consume()

    first = recommendation_service.get_suggestions(driver, "u", limit=10)
    repeated = recommendation_service.get_suggestions(driver, "u", limit=10)
    page = recommendation_service.get_suggestions(driver, "u", offset=1, limit=1)

    assert first == repeated
    assert [item["user_id"] for item in first["suggestions"]] == ["candidate", "later"]
    assert first["suggestions"][0] == {
        "user_id": "candidate",
        "name": "User candidate",
        "mutual_friends": 2,
    }
    assert [item["user_id"] for item in page["suggestions"]] == ["later"]
    assert "u" not in [item["user_id"] for item in first["suggestions"]]
    assert "existing" not in [item["user_id"] for item in first["suggestions"]]


def test_suggestions_reject_unknown_user(clean_graph):
    driver, _ = clean_graph
    with pytest.raises(AppError) as error:
        recommendation_service.get_suggestions(driver, "unknown")
    assert (error.value.code, error.value.status) == ("USER_NOT_FOUND", 404)


def test_pathfinding_through_a_thousand_degree_hub_within_timeout(clean_graph):
    driver, _ = clean_graph
    leaves = [f"leaf-{index:04d}" for index in range(1000)]
    _replace_graph(
        driver,
        ["hub", *leaves],
        [("hub", leaf) for leaf in leaves],
    )

    result = path_service.find_path(driver, leaves[0], leaves[-1])
    assert result["hops"] == 2
    assert [node["id"] for node in result["path"]][0] == leaves[0]
    assert [node["id"] for node in result["path"]][-1] == leaves[-1]
