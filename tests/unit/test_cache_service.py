import logging
import json
from pathlib import Path

import redis
import yaml

from app.db import redis_cache
from app.services.cache_service import CacheService
from app.services.friend_service import FriendService


class MemoryRedis:
    def __init__(self):
        self.values = {}
        self.ttls = {}

    def get(self, key):
        return self.values.get(key)

    def setex(self, key, ttl, value):
        self.values[key] = value
        self.ttls[key] = ttl

    def incr(self, key):
        value = int(self.values.get(key, 0)) + 1
        self.values[key] = str(value)
        return value


def test_keys_are_versioned_and_order_independent():
    assert CacheService.path_key(7, "c", "a") == "path:v7:a:c"
    assert CacheService.path_key(8, "a", "c") == "path:v8:a:c"


def test_paths_store_canonically_and_reverse_on_lookup():
    client = MemoryRedis()
    cache = CacheService(lambda: client)
    requested_path = [
        {"id": "c", "name": "C"},
        {"id": "b", "name": "B"},
        {"id": "a", "name": "A"},
    ]

    miss = cache.get_path("c", "a")
    assert (miss.version, miss.hit) == (0, False)
    cache.set_path("c", "a", requested_path, version=miss.version)

    forward = cache.get_path("a", "c")
    reverse = cache.get_path("c", "a")
    assert forward.hit is True
    assert [node["id"] for node in forward.path] == ["a", "b", "c"]
    assert [node["id"] for node in reverse.path] == ["c", "b", "a"]
    stored = json.loads(client.values["path:v0:a:c"])
    assert [node["id"] for node in stored["path"]] == ["a", "b", "c"]


def test_negative_entries_use_short_ttl_and_version_bump_invalidates_them():
    client = MemoryRedis()
    cache = CacheService(lambda: client, positive_ttl=300, negative_ttl=17)
    lookup = cache.get_path("a", "z")
    cache.set_path("a", "z", None, version=lookup.version)

    negative_key = "path:v0:a:z"
    negative = cache.get_path("z", "a")
    assert negative.hit is True and negative.path is None
    assert client.ttls[negative_key] == 17

    cache.bump_version()
    assert cache.get_path("a", "z").hit is False
    assert cache.get_path("a", "z").version == 1


def test_redis_failures_are_misses_and_warning_logs_are_rate_limited(caplog):
    class BrokenRedis:
        def get(self, _key):
            raise redis.ConnectionError("sensitive connection details")

        def incr(self, _key):
            raise redis.ConnectionError("sensitive connection details")

    cache = CacheService(lambda: BrokenRedis())
    with caplog.at_level(logging.WARNING):
        first = cache.get_path("a", "b")
        second = cache.get_path("a", "b")
        cache.bump_version()

    assert first.hit is second.hit is False
    assert first.version is second.version is None
    assert "sensitive connection details" not in caplog.text
    assert [record.operation for record in caplog.records] == [
        "read_version",
        "bump_version",
    ]


def test_first_cache_warning_is_not_suppressed_early_in_process_lifetime(
    caplog, monkeypatch
):
    class BrokenRedis:
        def get(self, _key):
            raise redis.ConnectionError("connection refused")

    monkeypatch.setattr("app.services.cache_service.time.monotonic", lambda: 1.0)
    cache = CacheService(lambda: BrokenRedis(), warning_interval_seconds=30)

    with caplog.at_level(logging.WARNING):
        cache.get_path("a", "b")

    assert [record.operation for record in caplog.records] == ["read_version"]


def test_failed_version_increment_is_fail_open_and_keeps_existing_ttl_bound():
    class BrokenIncrementRedis(MemoryRedis):
        def incr(self, _key):
            raise redis.ConnectionError("connection refused")

    client = BrokenIncrementRedis()
    cache = CacheService(lambda: client, positive_ttl=23)
    miss = cache.get_path("a", "b")
    cache.set_path(
        "a",
        "b",
        [{"id": "a", "name": "A"}, {"id": "b", "name": "B"}],
        version=miss.version,
    )

    cache.bump_version()

    assert cache.get_path("a", "b").hit is True
    assert client.ttls["path:v0:a:b"] == 23


def test_failed_version_increment_does_not_fail_friend_mutation(monkeypatch):
    class BrokenIncrementRedis(MemoryRedis):
        def incr(self, _key):
            raise redis.ConnectionError("connection refused")

    cache = CacheService(lambda: BrokenIncrementRedis())
    service = FriendService(on_graph_changed=cache.bump_version)
    monkeypatch.setattr(
        "app.services.friend_service.graph_repo.add_friendship",
        lambda *_args: (True, True),
    )

    assert service.add_friend(object(), "a", "b") == {"created": True}


def test_redis_client_uses_settings_timeouts(monkeypatch):
    captured = {}
    monkeypatch.setattr(redis_cache, "_client", None)
    monkeypatch.setattr(redis_cache.settings, "REDIS_URL", "redis://test.invalid/4")
    monkeypatch.setattr(redis_cache.settings, "REDIS_SOCKET_TIMEOUT_SECONDS", 0.17)

    def from_url(url, **options):
        captured["url"] = url
        captured.update(options)
        return object()

    monkeypatch.setattr(redis_cache.redis, "from_url", from_url)
    redis_cache.get_client()

    assert captured == {
        "url": "redis://test.invalid/4",
        "decode_responses": True,
        "socket_timeout": 0.17,
        "socket_connect_timeout": 0.17,
    }


def test_prod_redis_cache_keeps_version_key_out_of_lru_eviction():
    compose = yaml.safe_load(
        Path("docker-compose.prod.yml").read_text(encoding="utf-8")
    )
    redis_command = compose["services"]["redis"]["command"]

    assert (
        redis_command[redis_command.index("--maxmemory-policy") + 1] == "volatile-lru"
    )
    assert redis_command[redis_command.index("--appendonly") + 1] == "no"
    assert redis_command[redis_command.index("--save") + 1] == ""
