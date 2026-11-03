from unittest.mock import ANY, patch

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_current_user
from app.core.security import create_access_token
from app.db.neo4j_db import get_driver
from app.db.redis_cache import get_client
from app.domain.errors import AppError, RateLimitedError
from app.main import app

client = TestClient(app)


class RedisStub:
    def eval(self, *_args):
        return [1, 60]


class BrokenRedis:
    def eval(self, *_args):
        raise OSError("unavailable")


@pytest.fixture
def authenticated_client():
    previous = app.dependency_overrides.copy()
    app.dependency_overrides[get_current_user] = lambda: {"user_id": "test-user"}
    app.dependency_overrides[get_client] = RedisStub
    yield client
    app.dependency_overrides.clear()
    app.dependency_overrides.update(previous)


def _register_payload(**overrides):
    return {
        "name": "Alice",
        "email": "alice@example.com",
        "password": "a-long-password",
        **overrides,
    }


def test_health_check_is_live_without_dependencies():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_removed_user_creation_and_arbitrary_connections_routes():
    assert client.post("/api/v1/users/", json={}).status_code in {404, 405}
    assert client.post(
        "/api/v1/connections", json={"user_id_1": "a", "user_id_2": "b"}
    ).status_code in {404, 405}


def test_register_validates_payload_before_service_call():
    response = client.post(
        "/api/v1/auth/register", json=_register_payload(password="short")
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
    assert all("input" not in item for item in response.json()["error"]["details"])


def test_register_delegates_and_returns_token_contract(monkeypatch):
    previous = app.dependency_overrides.copy()
    app.dependency_overrides[get_driver] = lambda: object()
    app.dependency_overrides[get_client] = RedisStub
    result = {"access_token": "token", "token_type": "bearer", "expires_in": 1800}
    received = {}

    def register(*_args, **kwargs):
        received.update(kwargs)
        return result

    monkeypatch.setattr("app.api.routes_auth.auth_service.register", register)
    response = client.post(
        "/api/v1/auth/register",
        json=_register_payload(),
        headers={"X-Forwarded-For": "198.51.100.55"},
    )
    app.dependency_overrides.clear()
    app.dependency_overrides.update(previous)
    assert response.status_code == 201
    assert response.json() == result
    assert received["client_ip"] == "testclient"


def test_rate_limit_error_uses_http_retry_after_header(monkeypatch):
    previous = app.dependency_overrides.copy()
    app.dependency_overrides[get_client] = RedisStub

    def limited(*_args, **_kwargs):
        raise RateLimitedError(35)

    monkeypatch.setattr("app.api.routes_auth.auth_service.register", limited)
    response = client.post("/api/v1/auth/register", json=_register_payload())
    app.dependency_overrides.clear()
    app.dependency_overrides.update(previous)
    assert response.status_code == 429
    assert response.headers["Retry-After"] == "35"
    assert response.json()["error"]["code"] == "RATE_LIMITED"


def test_unknown_and_wrong_credentials_have_identical_error_envelope(monkeypatch):
    previous = app.dependency_overrides.copy()
    app.dependency_overrides[get_client] = RedisStub

    def invalid_credentials(*_args, **_kwargs):
        raise AppError("UNAUTHENTICATED", "Incorrect email or password.", 401)

    monkeypatch.setattr("app.api.routes_auth.auth_service.login", invalid_credentials)
    headers = {"X-Request-ID": "same-request-id"}
    first = client.post(
        "/api/v1/auth/token",
        data={"username": "known@example.com", "password": "wrong"},
        headers=headers,
    )
    second = client.post(
        "/api/v1/auth/token",
        data={"username": "missing@example.com", "password": "wrong"},
        headers=headers,
    )
    app.dependency_overrides.clear()
    app.dependency_overrides.update(previous)
    assert first.status_code == second.status_code == 401
    assert first.json() == second.json()


def test_login_fails_closed_when_redis_is_unavailable():
    previous = app.dependency_overrides.copy()
    app.dependency_overrides[get_client] = BrokenRedis
    response = client.post(
        "/api/v1/auth/token",
        data={"username": "alice@example.com", "password": "some-password"},
    )
    app.dependency_overrides.clear()
    app.dependency_overrides.update(previous)
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "UNAVAILABLE"


def test_search_fails_open_when_redis_is_unavailable(authenticated_client):
    app.dependency_overrides[get_client] = BrokenRedis
    with patch(
        "app.api.routes_users.user_service.search_users",
        return_value=[{"id": "friend", "name": "Friend", "source": "snap"}],
    ):
        response = authenticated_client.get("/api/v1/users/search?q=fr")
    assert response.status_code == 200


def test_public_profile_requires_auth_and_never_returns_email(authenticated_client):
    public_user = {"id": "friend", "name": "Friend", "source": "app"}
    with patch("app.api.routes_users.user_service.get_user", return_value=public_user):
        response = authenticated_client.get("/api/v1/users/friend")
    assert response.status_code == 200
    assert "email" not in response.json()
    assert "password_hash" not in response.json()


def test_public_profile_remains_available_when_redis_is_down(authenticated_client):
    app.dependency_overrides[get_client] = BrokenRedis
    with patch(
        "app.api.routes_users.user_service.get_user",
        return_value={"id": "friend", "name": "Friend", "source": "snap"},
    ):
        response = authenticated_client.get("/api/v1/users/friend")
    assert response.status_code == 200


def test_search_is_protected_and_uses_public_projection(authenticated_client):
    users = [{"id": "friend", "name": "Friend", "source": "snap"}]
    with patch("app.api.routes_users.user_service.search_users", return_value=users):
        response = authenticated_client.get("/api/v1/users/search?q=fr")
    assert response.status_code == 200
    assert response.json() == users
    assert "email" not in response.text
    assert "password_hash" not in response.text


def test_own_profile_can_include_only_own_email(authenticated_client):
    profile = {
        "id": "test-user",
        "name": "Alice",
        "source": "app",
        "email": "alice@example.com",
    }
    with patch("app.api.routes_users.user_repo.get_own_profile", return_value=profile):
        response = authenticated_client.get("/api/v1/users/me")
    assert response.status_code == 200
    assert response.json()["email"] == profile["email"]
    assert "password_hash" not in response.text


def test_profile_update_changes_name_only(authenticated_client):
    profile = {
        "id": "test-user",
        "name": "Alicia",
        "source": "app",
        "email": "alice@example.com",
    }
    with (
        patch("app.api.routes_users.user_service.update_user") as update,
        patch("app.api.routes_users.user_repo.get_own_profile", return_value=profile),
    ):
        response = authenticated_client.put("/api/v1/users/me", json={"name": "Alicia"})
    assert response.status_code == 200
    update.assert_called_once_with(ANY, "test-user", "Alicia")
    assert response.json()["email"] == "alice@example.com"
    rejected = authenticated_client.put(
        "/api/v1/users/me", json={"name": "Alicia", "email": "other@example.com"}
    )
    assert rejected.status_code == 422


def test_protected_user_routes_reject_missing_token():
    for path in ("/api/v1/users/me", "/api/v1/users/x", "/api/v1/users/search?q=ab"):
        response = client.get(path)
        assert response.status_code == 401
        assert response.json()["error"]["code"] == "UNAUTHENTICATED"


def test_current_user_rejects_token_for_deleted_user(monkeypatch):
    from app.repositories import user_repo

    monkeypatch.setattr(user_repo, "user_exists", lambda *_args: False)
    response = client.get(
        "/api/v1/users/me",
        headers={"Authorization": f"Bearer {create_access_token('deleted-user')}"},
    )
    assert response.status_code == 401


def test_current_user_rejects_non_object_jwt_payload(monkeypatch):
    monkeypatch.setattr("app.api.deps.decode_access_token", lambda _token: [])
    response = client.get(
        "/api/v1/users/me",
        headers={"Authorization": f"Bearer {create_access_token('user')}"},
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHENTICATED"


def test_legacy_path_endpoint_remains_functional(authenticated_client):
    cached = {
        "start_user": "0",
        "end_user": "150",
        "path": ["0", "107", "150"],
        "hops": 2,
        "cached": False,
    }
    with patch(
        "app.services.pathfinder.redis_cache.get_cached_path", return_value=cached
    ):
        response = authenticated_client.get("/api/v1/path/0/150")
    assert response.status_code == 200
    assert response.json()["cached"] is True
    assert response.json()["path"] == ["0", "107", "150"]


def test_legacy_suggestions_endpoint_remains_functional(authenticated_client):
    with patch(
        "app.services.pathfinder.graph_repo.get_friend_suggestions",
        return_value=[("friend", 3)],
    ):
        response = authenticated_client.get("/api/v1/suggestions/0")
    assert response.status_code == 200
    assert response.json()["suggestions"][0]["user_id"] == "friend"


def test_friend_route_remains_scoped_to_authenticated_caller(authenticated_client):
    with (
        patch(
            "app.api.routes_friends.user_repo.get_user_by_id",
            return_value={"id": "friend", "name": "Friend"},
        ),
        patch(
            "app.api.routes_friends.graph_repo.create_connection"
        ) as create_connection,
    ):
        response = authenticated_client.post("/friends/friend")
    assert response.status_code == 201
    create_connection.assert_called_once_with(ANY, "test-user", "friend")
