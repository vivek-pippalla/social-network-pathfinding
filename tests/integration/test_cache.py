import multiprocessing
import os
import time

import pytest
import redis
from fastapi.testclient import TestClient

from app.api.deps import get_current_user
from app.core.config import settings
from app.db.neo4j_db import get_driver
from app.domain.errors import AppError
from app.services.cache_service import CacheService
from app.services.friend_service import FriendService
from app.services.path_service import find_path

pytestmark = pytest.mark.integration


def _cache_api_worker(worker_id, commands, results):
    from neo4j import GraphDatabase

    from app.api.deps import get_current_user
    from app.core.config import get_settings
    from app.db.neo4j_db import get_driver
    from app.main import create_app

    driver = GraphDatabase.driver(
        os.getenv("TEST_NEO4J_URI", "bolt://127.0.0.1:17687"),
        auth=(
            os.getenv("TEST_NEO4J_USER", "neo4j"),
            os.getenv("TEST_NEO4J_PASSWORD", "integration-test-password"),
        ),
    )
    redis_client = redis.Redis.from_url(
        os.getenv("TEST_REDIS_URL", "redis://127.0.0.1:16379/15"),
        decode_responses=True,
        socket_timeout=settings.REDIS_SOCKET_TIMEOUT_SECONDS,
        socket_connect_timeout=settings.REDIS_SOCKET_TIMEOUT_SECONDS,
    )
    application = create_app(
        get_settings().model_copy(update={"AUTO_SCHEMA": False}),
        driver_provider=lambda: driver,
        redis_provider=lambda: redis_client,
        driver_closer=lambda: None,
    )
    application.dependency_overrides[get_driver] = lambda: driver
    application.dependency_overrides[get_current_user] = lambda: {"user_id": "a"}

    try:
        with TestClient(application) as client:
            results.put(("ready", worker_id))
            while True:
                action = commands.get()
                if action == "stop":
                    return
                if action == "path":
                    response = client.get("/api/v1/path/a/c")
                    results.put(
                        ("path", worker_id, response.status_code, response.json())
                    )
                elif action == "add_friend":
                    response = client.post("/api/v1/friends/c")
                    results.put(("add_friend", worker_id, response.status_code))
    except BaseException as exc:
        results.put(("error", worker_id, repr(exc)))
        raise
    finally:
        redis_client.close()
        driver.close()


def _create_graph(driver, user_ids: list[str], edges: list[tuple[str, str]]) -> None:
    def write_graph(tx):
        tx.run(
            "UNWIND $ids AS id CREATE (:User {id: id, name: 'User ' + id})",
            ids=user_ids,
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


def _cache(redis_client, *, positive_ttl=300, negative_ttl=60):
    return CacheService(
        lambda: redis_client,
        positive_ttl=positive_ttl,
        negative_ttl=negative_ttl,
    )


def test_path_cache_reverse_query_returns_reoriented_path(clean_graph):
    driver, redis_client = clean_graph
    _create_graph(driver, ["a", "b", "c"], [("a", "b"), ("b", "c")])
    cache = _cache(redis_client)

    first = find_path(driver, "a", "c", cache)
    reverse = find_path(driver, "c", "a", cache)

    assert first["cached"] is False
    assert reverse["cached"] is True
    assert (reverse["start_user"], reverse["end_user"]) == ("c", "a")
    assert [node["id"] for node in reverse["path"]] == ["c", "b", "a"]


def test_friend_add_and_remove_invalidate_shortened_path(clean_graph):
    driver, redis_client = clean_graph
    _create_graph(
        driver,
        ["a", "b", "c", "d"],
        [("a", "b"), ("b", "c"), ("c", "d")],
    )
    cache = _cache(redis_client)
    friends = FriendService(on_graph_changed=cache.bump_version)

    original = find_path(driver, "a", "d", cache)
    friends.add_friend(driver, "a", "d")
    shortened = find_path(driver, "a", "d", cache)
    friends.remove_friend(driver, "a", "d")
    restored = find_path(driver, "a", "d", cache)

    assert original["hops"] == 3 and original["cached"] is False
    assert shortened["hops"] == 1 and shortened["cached"] is False
    assert restored["hops"] == 3 and restored["cached"] is False


def test_negative_entry_is_short_lived_and_invalidated_after_connecting(clean_graph):
    driver, redis_client = clean_graph
    _create_graph(driver, ["a", "z"], [])
    cache = _cache(redis_client, negative_ttl=19)
    friends = FriendService(on_graph_changed=cache.bump_version)

    with pytest.raises(AppError) as first:
        find_path(driver, "a", "z", cache)
    negative_key = cache.path_key(0, "a", "z")
    ttl = redis_client.ttl(negative_key)
    with pytest.raises(AppError) as repeated:
        find_path(driver, "z", "a", cache)
    friends.add_friend(driver, "a", "z")
    connected = find_path(driver, "a", "z", cache)

    assert (first.value.code, repeated.value.code) == (
        "PATH_NOT_FOUND",
        "PATH_NOT_FOUND",
    )
    assert 0 < ttl <= 19
    assert connected["hops"] == 1 and connected["cached"] is False


def test_losing_redis_cache_does_not_lose_path_data(clean_graph):
    driver, redis_client = clean_graph
    _create_graph(driver, ["a", "b"], [("a", "b")])
    cache = _cache(redis_client)

    assert find_path(driver, "a", "b", cache)["cached"] is False
    redis_client.flushdb()
    after_cache_loss = find_path(driver, "a", "b", cache)
    restored_cache = find_path(driver, "a", "b", cache)

    assert after_cache_loss["hops"] == 1 and after_cache_loss["cached"] is False
    assert restored_cache["hops"] == 1 and restored_cache["cached"] is True


def test_independent_api_processes_share_graph_version_invalidation(clean_graph):
    driver, _redis_client = clean_graph
    _create_graph(driver, ["a", "b", "c"], [("a", "b"), ("b", "c")])
    context = multiprocessing.get_context("spawn")
    results = context.Queue()
    commands = [context.Queue(), context.Queue()]
    workers = [
        context.Process(target=_cache_api_worker, args=(i, commands[i], results))
        for i in range(2)
    ]
    try:
        for worker in workers:
            worker.start()
        ready = {results.get(timeout=15) for _ in workers}
        assert ready == {("ready", 0), ("ready", 1)}

        commands[0].put("path")
        initial = results.get(timeout=15)
        commands[1].put("add_friend")
        mutation = results.get(timeout=15)
        commands[0].put("path")
        after_mutation = results.get(timeout=15)

        assert initial[:3] == ("path", 0, 200)
        assert initial[3]["hops"] == 2
        assert mutation == ("add_friend", 1, 201)
        assert after_mutation[:3] == ("path", 0, 200)
        assert after_mutation[3]["hops"] == 1
        assert after_mutation[3]["cached"] is False
    finally:
        for command_queue in commands:
            command_queue.put("stop")
        for worker in workers:
            worker.join(timeout=10)
            if worker.is_alive():
                worker.terminate()
                worker.join(timeout=5)


def test_unavailable_redis_does_not_delay_or_break_path_api(clean_graph):
    driver, _redis_client = clean_graph
    _create_graph(driver, ["a", "b"], [("a", "b")])
    unavailable_client = redis.Redis.from_url(
        "redis://127.0.0.1:1/15",
        decode_responses=True,
        socket_timeout=settings.REDIS_SOCKET_TIMEOUT_SECONDS,
        socket_connect_timeout=settings.REDIS_SOCKET_TIMEOUT_SECONDS,
    )
    from app.main import create_app

    application = create_app(
        settings.model_copy(update={"AUTO_SCHEMA": False}),
        driver_provider=lambda: driver,
        redis_provider=lambda: unavailable_client,
        driver_closer=lambda: None,
    )
    application.dependency_overrides[get_driver] = lambda: driver
    application.dependency_overrides[get_current_user] = lambda: {"user_id": "a"}
    started = time.perf_counter()
    with TestClient(application) as client:
        response = client.get("/api/v1/path/a/b")
    elapsed = time.perf_counter() - started

    assert response.status_code == 200
    assert response.json()["hops"] == 1 and response.json()["cached"] is False
    assert elapsed < settings.NEO4J_QUERY_TIMEOUT_SECONDS + 1.0
