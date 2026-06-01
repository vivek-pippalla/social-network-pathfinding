"""
Full test suite for the Social Network Pathfinding API.

Strategy
--------
- FastAPI's TestClient simulates real HTTP requests with no running server.
- All Neo4j and Redis calls are mocked at the repository / cache layer so the
  tests pass in CI with zero infrastructure.
- JWT-protected endpoints use a pytest fixture that overrides get_current_user,
  keeping auth logic out of unrelated test cases.
- Auth-specific tests generate real tokens so the full JWT encode/decode path
  is exercised.

Run with:  pytest tests/ -v
"""

import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient

from app.main import app
from app.core.auth import get_current_user, create_access_token

client = TestClient(app)

# ─── Fixture: bypass JWT for graph-layer tests ─────────────────────────────

@pytest.fixture
def auth(monkeypatch):
    """Override JWT dependency so graph-endpoint tests don't need a token."""
    app.dependency_overrides[get_current_user] = lambda: {"user_id": "test-user-id"}
    yield
    app.dependency_overrides.clear()


def make_token(user_id: str = "test-user-id") -> str:
    """Generate a real JWT for auth-endpoint tests."""
    return create_access_token({"sub": user_id})


# ═══════════════════════════════════════════════════════════════════════════
# 1 — Health check
# ═══════════════════════════════════════════════════════════════════════════

def test_health_check():
    """GET /health must return 200 and status='ok'."""
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"


# ═══════════════════════════════════════════════════════════════════════════
# 2 — User endpoints
# ═══════════════════════════════════════════════════════════════════════════

def test_create_user_missing_name_returns_422():
    """Pydantic rejects a body with no 'name' — 422 Unprocessable Entity."""
    res = client.post("/api/v1/users/", json={})
    assert res.status_code == 422


def test_create_user_success():
    """POST /users/ with valid body returns 201 and the created user."""
    mock_user = {"id": "abc12345", "name": "Alice", "email": "alice@test.com"}
    with patch("app.services.user_service.user_repo.create_user", return_value=mock_user):
        res = client.post("/api/v1/users/", json={"name": "Alice", "email": "alice@test.com"})
    assert res.status_code == 201
    data = res.json()
    assert data["id"] == "abc12345"
    assert data["name"] == "Alice"


def test_get_user_by_id_success():
    """GET /users/{id} returns the user when found."""
    mock_user = {"id": "abc12345", "name": "Alice", "email": "alice@test.com"}
    with patch("app.services.user_service.user_repo.get_user_by_id", return_value=mock_user):
        res = client.get("/api/v1/users/abc12345")
    assert res.status_code == 200
    assert res.json()["name"] == "Alice"


def test_get_nonexistent_user_returns_404():
    """GET /users/{id} returns 404 for an unknown user (UserNotFoundException)."""
    with patch("app.services.user_service.user_repo.get_user_by_id", return_value=None):
        res = client.get("/api/v1/users/does-not-exist")
    assert res.status_code == 404
    assert "not found" in res.json()["detail"].lower()


def test_search_users_returns_list():
    """GET /users/search?q= returns a list of matching users."""
    mock_users = [
        {"id": "aaa", "name": "Alice Smith", "email": None},
        {"id": "bbb", "name": "Alice Jones", "email": None},
    ]
    with patch("app.services.user_service.user_repo.search_users", return_value=mock_users):
        res = client.get("/api/v1/users/search?q=alice")
    assert res.status_code == 200
    assert len(res.json()) == 2
    assert res.json()[0]["name"] == "Alice Smith"


# ═══════════════════════════════════════════════════════════════════════════
# 3 — Auth endpoints
# ═══════════════════════════════════════════════════════════════════════════

def test_register_success():
    """POST /auth/register creates a user and returns a JWT token."""
    mock_created = {"id": "new001", "name": "Bob", "email": "bob@test.com"}
    with patch("app.api.routes_auth.user_repo.get_user_by_email", return_value=None), \
         patch("app.api.routes_auth.user_repo.create_user_with_password", return_value=mock_created):
        res = client.post("/api/v1/auth/register", json={
            "name": "Bob",
            "email": "bob@test.com",
            "password": "secret123",
        })
    assert res.status_code == 201
    data = res.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


def test_register_duplicate_email_returns_409():
    """POST /auth/register with an already-registered email returns 409."""
    existing = {"id": "old001", "name": "Bob", "email": "bob@test.com"}
    with patch("app.api.routes_auth.user_repo.get_user_by_email", return_value=existing):
        res = client.post("/api/v1/auth/register", json={
            "name": "Bob Again",
            "email": "bob@test.com",
            "password": "secret123",
        })
    assert res.status_code == 409


def test_login_success():
    """POST /auth/token with correct credentials returns a JWT token."""
    from app.core.auth import hash_password
    hashed = hash_password("secret123")
    mock_user = {"id": "usr001", "name": "Bob", "email": "bob@test.com", "password_hash": hashed}

    with patch("app.api.routes_auth.user_repo.get_user_by_email", return_value=mock_user):
        res = client.post("/api/v1/auth/token", data={
            "username": "bob@test.com",
            "password": "secret123",
        })
    assert res.status_code == 200
    assert "access_token" in res.json()


def test_login_wrong_password_returns_401():
    """POST /auth/token with wrong password returns 401."""
    from app.core.auth import hash_password
    hashed = hash_password("correct-password")
    mock_user = {"id": "usr001", "name": "Bob", "email": "bob@test.com", "password_hash": hashed}

    with patch("app.api.routes_auth.user_repo.get_user_by_email", return_value=mock_user):
        res = client.post("/api/v1/auth/token", data={
            "username": "bob@test.com",
            "password": "wrong-password",
        })
    assert res.status_code == 401


def test_login_unknown_email_returns_401():
    """POST /auth/token with an unrecognised email returns 401."""
    with patch("app.api.routes_auth.user_repo.get_user_by_email", return_value=None):
        res = client.post("/api/v1/auth/token", data={
            "username": "ghost@nowhere.com",
            "password": "anything",
        })
    assert res.status_code == 401


# ═══════════════════════════════════════════════════════════════════════════
# 4 — JWT guard on protected endpoints
# ═══════════════════════════════════════════════════════════════════════════

def test_path_endpoint_requires_auth():
    """GET /path/… without a token must return 401."""
    res = client.get("/api/v1/path/0/150")
    assert res.status_code == 401


def test_suggestions_endpoint_requires_auth():
    """GET /suggestions/… without a token must return 401."""
    res = client.get("/api/v1/suggestions/0")
    assert res.status_code == 401


def test_connections_endpoint_requires_auth():
    """POST /connections without a token must return 401."""
    res = client.post("/api/v1/connections", json={"user_id_1": "0", "user_id_2": "1"})
    assert res.status_code == 401


# ═══════════════════════════════════════════════════════════════════════════
# 5 — Pathfinding (authenticated)
# ═══════════════════════════════════════════════════════════════════════════

def test_path_returns_cached_result(auth):
    """When Redis has a cached entry, return it immediately with cached=True."""
    cached = {
        "start_user": "0", "end_user": "150",
        "path": ["0", "107", "150"],
        "hops": 2, "cached": False,
    }
    with patch("app.services.pathfinder.redis_cache.get_cached_path", return_value=cached):
        res = client.get("/api/v1/path/0/150")

    assert res.status_code == 200
    data = res.json()
    assert data["hops"] == 2
    assert data["path"] == ["0", "107", "150"]
    assert data["cached"] is True          # pathfinder flips this on cache hit


def test_path_queries_neo4j_on_cache_miss(auth):
    """On a cache miss, Neo4j is queried and the result is cached."""
    with patch("app.services.pathfinder.redis_cache.get_cached_path", return_value=None), \
         patch("app.services.pathfinder.graph_repo.find_shortest_path", return_value=["0", "107", "150"]), \
         patch("app.services.pathfinder.redis_cache.set_cached_path") as mock_set:
        res = client.get("/api/v1/path/0/150")

    assert res.status_code == 200
    data = res.json()
    assert data["hops"] == 2
    assert data["cached"] is False         # came from Neo4j, not cache
    mock_set.assert_called_once()          # result was stored in Redis


def test_path_not_found_returns_404(auth):
    """When no path exists, the endpoint returns 404."""
    with patch("app.services.pathfinder.redis_cache.get_cached_path", return_value=None), \
         patch("app.services.pathfinder.graph_repo.find_shortest_path", return_value=None):
        res = client.get("/api/v1/path/0/9999")
    assert res.status_code == 404


# ═══════════════════════════════════════════════════════════════════════════
# 6 — Connections & Suggestions (authenticated)
# ═══════════════════════════════════════════════════════════════════════════

def test_create_connection_success(auth):
    """POST /connections creates a link and returns a confirmation message."""
    with patch("app.api.routes_graph.graph_repo.create_connection", return_value=None):
        res = client.post("/api/v1/connections", json={"user_id_1": "0", "user_id_2": "1"})
    assert res.status_code == 201
    assert "created" in res.json()["message"].lower()


def test_get_suggestions_returns_list(auth):
    """GET /suggestions returns ranked friend-of-friend suggestions."""
    mock_raw = [("200", 5), ("300", 3), ("400", 1)]
    with patch("app.services.pathfinder.graph_repo.get_friend_suggestions", return_value=mock_raw):
        res = client.get("/api/v1/suggestions/0")
    assert res.status_code == 200
    data = res.json()
    assert data["user_id"] == "0"
    assert len(data["suggestions"]) == 3
    assert data["suggestions"][0]["user_id"] == "200"
    assert data["suggestions"][0]["mutual_friends"] == 5
