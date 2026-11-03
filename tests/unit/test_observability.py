import json
import logging
from unittest.mock import Mock

import pytest
import redis
from prometheus_client import REGISTRY
from fastapi.testclient import TestClient

from app.core.logging import JSONFormatter
from app.core.metrics import (
    AUTH_FAILURES,
    FRIEND_MUTATIONS,
    NEO4J_QUERY_DURATION,
    PATH_CACHE_OPERATIONS,
    PATH_REQUEST_DURATION,
    RATE_LIMIT_REJECTIONS,
)
from app.core.observability import email_identifier
from app.core.rate_limit import RateLimitedError, check_search
from app.domain.errors import AppError
from app.main import app
from app.repositories import graph_repo
from app.services import auth_service, path_service
from app.services.cache_service import CacheService, PathCacheLookup
from app.services.friend_service import FriendService


def _counter_value(name, labels):
    return REGISTRY.get_sample_value(name, labels) or 0


class MemoryRedis:
    def __init__(self):
        self.values = {}

    def get(self, key):
        return self.values.get(key)

    def setex(self, key, _ttl, value):
        self.values[key] = value


def test_cache_hit_miss_and_error_counters_move_with_cache_operations():
    client = MemoryRedis()
    cache = CacheService(lambda: client)
    miss_before = _counter_value("path_cache_operations_total", {"result": "miss"})
    hit_before = _counter_value("path_cache_operations_total", {"result": "hit"})
    error_before = _counter_value("path_cache_operations_total", {"result": "error"})

    first = cache.get_path("a", "b")
    cache.set_path(
        "a",
        "b",
        [{"id": "a", "name": "A"}, {"id": "b", "name": "B"}],
        version=first.version,
    )
    assert cache.get_path("a", "b").hit

    class BrokenRedis:
        def get(self, _key):
            raise redis.ConnectionError("cache failure")

    CacheService(lambda: BrokenRedis()).get_path("a", "b")
    assert (
        _counter_value("path_cache_operations_total", {"result": "miss"})
        == miss_before + 2
    )
    assert (
        _counter_value("path_cache_operations_total", {"result": "hit"})
        == hit_before + 1
    )
    assert (
        _counter_value("path_cache_operations_total", {"result": "error"})
        == error_before + 1
    )


def test_path_duration_histogram_uses_cache_hit_and_miss_labels(monkeypatch):
    monkeypatch.setattr(
        path_service.graph_repo,
        "get_users_by_ids",
        lambda _driver, _ids: {
            "a": {"id": "a", "name": "A"},
            "b": {"id": "b", "name": "B"},
        },
    )
    monkeypatch.setattr(
        path_service.graph_repo,
        "find_bounded_shortest_path",
        lambda *_args: [{"id": "a", "name": "A"}, {"id": "b", "name": "B"}],
    )
    miss_before = _counter_value(
        "path_request_duration_seconds_count", {"cache": "miss"}
    )
    hit_before = _counter_value("path_request_duration_seconds_count", {"cache": "hit"})
    path_service.find_path(object(), "a", "b")

    class CacheHit:
        def get_path(self, *_args):
            return PathCacheLookup(
                version=1,
                hit=True,
                path=[{"id": "a", "name": "A"}, {"id": "b", "name": "B"}],
            )

    path_service.find_path(object(), "a", "b", CacheHit())
    assert (
        _counter_value("path_request_duration_seconds_count", {"cache": "miss"})
        == miss_before + 1
    )
    assert (
        _counter_value("path_request_duration_seconds_count", {"cache": "hit"})
        == hit_before + 1
    )


def test_friend_mutation_metrics_cover_all_outcomes(monkeypatch):
    service = FriendService()
    add_before = _counter_value("friend_mutations_total", {"outcome": "created"})
    exists_before = _counter_value("friend_mutations_total", {"outcome": "exists"})
    remove_before = _counter_value("friend_mutations_total", {"outcome": "removed"})
    noop_before = _counter_value("friend_mutations_total", {"outcome": "noop"})
    monkeypatch.setattr(
        "app.services.friend_service.graph_repo.add_friendship",
        Mock(side_effect=[(True, True), (True, False)]),
    )
    monkeypatch.setattr(
        "app.services.friend_service.graph_repo.remove_friendship",
        Mock(side_effect=[(True, True), (True, False)]),
    )

    service.add_friend(object(), "a", "b")
    service.add_friend(object(), "a", "b")
    service.remove_friend(object(), "a", "b")
    service.remove_friend(object(), "a", "b")
    assert (
        _counter_value("friend_mutations_total", {"outcome": "created"})
        == add_before + 1
    )
    assert (
        _counter_value("friend_mutations_total", {"outcome": "exists"})
        == exists_before + 1
    )
    assert (
        _counter_value("friend_mutations_total", {"outcome": "removed"})
        == remove_before + 1
    )
    assert (
        _counter_value("friend_mutations_total", {"outcome": "noop"}) == noop_before + 1
    )


def test_auth_failure_and_email_fingerprint_are_safe_in_structured_logs(
    monkeypatch, caplog
):
    email = "person-private@example.test"
    password = "password-private-sentinel"
    monkeypatch.setattr(auth_service.rate_limit, "check_login", lambda *_args: None)
    monkeypatch.setattr(
        auth_service.account_repo, "get_account_by_email", lambda *_args: None
    )
    monkeypatch.setattr(auth_service, "dummy_password_hash", lambda: "dummy")
    monkeypatch.setattr(auth_service, "verify_password", lambda *_args: False)
    before = _counter_value(
        "auth_failures_total", {"operation": "login", "reason": "invalid_credentials"}
    )

    with caplog.at_level(logging.WARNING, logger="app.services.auth_service"):
        with pytest.raises(AppError):
            auth_service.login(
                object(),
                object(),
                client_ip="127.0.0.1",
                email=email,
                password=password,
            )

    assert (
        _counter_value(
            "auth_failures_total",
            {"operation": "login", "reason": "invalid_credentials"},
        )
        == before + 1
    )
    record = next(
        record
        for record in caplog.records
        if record.name == "app.services.auth_service"
    )
    encoded = JSONFormatter().format(record)
    event = json.loads(encoded)
    assert event["event"] == "login_failed"
    assert event["email_hash"] == email_identifier(email)
    assert email not in encoded and password not in encoded


def test_authorization_header_is_not_written_to_request_logs(caplog):
    token = "authorization-token-private-sentinel"
    with caplog.at_level(logging.INFO):
        response = TestClient(app).get(
            "/api/v1/users/me", headers={"Authorization": f"Bearer {token}"}
        )
    assert response.status_code == 401
    rendered = "\n".join(JSONFormatter().format(record) for record in caplog.records)
    assert token not in rendered
    assert "Authorization" not in rendered


def test_rate_limit_rejection_counter_moves_and_logs_no_client_details(caplog):
    class LimitedRedis:
        def eval(self, *_args):
            return [31, 20]

    before = _counter_value("rate_limit_rejections_total", {"operation": "search"})
    with caplog.at_level(logging.WARNING, logger="app.core.rate_limit"):
        with pytest.raises(RateLimitedError):
            check_search(LimitedRedis(), "198.51.100.77")
    assert (
        _counter_value("rate_limit_rejections_total", {"operation": "search"})
        == before + 1
    )
    record = next(
        record for record in caplog.records if record.name == "app.core.rate_limit"
    )
    assert json.loads(JSONFormatter().format(record))["event"] == "rate_limit_rejected"
    assert "198.51.100.77" not in JSONFormatter().format(record)


def test_neo4j_repository_operation_duration_is_recorded():
    class Result:
        def single(self):
            return None

    class Transaction:
        def run(self, *_args, **_kwargs):
            return Result()

    class Session:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def execute_read(self, callback):
            return callback(Transaction())

    class Driver:
        def session(self):
            return Session()

    operation = "graph.find_bounded_shortest_path"
    before = _counter_value(
        "neo4j_query_duration_seconds_count", {"operation": operation}
    )
    assert graph_repo.find_bounded_shortest_path(Driver(), "a", "b", 3) is None
    assert (
        _counter_value("neo4j_query_duration_seconds_count", {"operation": operation})
        == before + 1
    )


def test_friend_and_cache_failure_logs_are_structured_without_sensitive_values(
    monkeypatch, caplog
):
    friend_ids = ("private-user-id-a", "private-user-id-b")
    monkeypatch.setattr(
        "app.services.friend_service.graph_repo.add_friendship",
        lambda *_args: (True, True),
    )

    class BrokenRedis:
        def get(self, _key):
            raise redis.ConnectionError("private-redis-host-sentinel")

    with caplog.at_level(logging.INFO):
        FriendService().add_friend(object(), *friend_ids)
        CacheService(lambda: BrokenRedis()).get_path("a", "b")

    serialized = [JSONFormatter().format(record) for record in caplog.records]
    friend_event = next(
        json.loads(line) for line in serialized if '"friend_added"' in line
    )
    cache_event = next(
        json.loads(line) for line in serialized if '"cache_error"' in line
    )
    assert friend_event["event"] == "friend_added"
    assert friend_event["outcome"] == "created"
    assert cache_event["event"] == "cache_error"
    combined = "\n".join(serialized)
    assert all(
        value not in combined for value in (*friend_ids, "private-redis-host-sentinel")
    )


def test_sensitive_label_values_are_not_present_in_metric_definitions():
    metrics = (
        PATH_CACHE_OPERATIONS,
        PATH_REQUEST_DURATION,
        FRIEND_MUTATIONS,
        AUTH_FAILURES,
        RATE_LIMIT_REJECTIONS,
        NEO4J_QUERY_DURATION,
    )
    for metric in metrics:
        assert set(metric._labelnames) <= {
            "result",
            "cache",
            "outcome",
            "operation",
            "reason",
        }
