"""
Basic API tests for the Social Network Pathfinding Engine.
Run with: pytest tests/ -v

These tests use FastAPI's TestClient which simulates real HTTP requests
without needing a running server or actual database connections.
"""
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
from app.main import app

client = TestClient(app)


# ─── Health Check ────────────────────────────────────────────────────────────

def test_health_check():
    """API should return 200 and status 'ok'."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


# ─── User Endpoints ──────────────────────────────────────────────────────────

def test_create_user_missing_name_returns_422():
    """
    Pydantic should reject a request with no 'name' field.
    422 = Unprocessable Entity (validation error).
    """
    response = client.post("/api/v1/users/", json={})
    assert response.status_code == 422


def test_get_nonexistent_user_returns_404():
    """
    Fetching a user ID that doesn't exist should return 404.
    This tests our custom UserNotFoundException.
    """
    with patch("app.services.user_service.user_repo.get_user_by_id", return_value=None):
        response = client.get("/api/v1/users/nonexistent_id")
    assert response.status_code == 404


# ─── Pathfinding Endpoint ────────────────────────────────────────────────────

def test_path_endpoint_returns_cached_result():
    """
    When Redis has a cached path, the endpoint should return it
    immediately with cached=True, without hitting Neo4j.
    """
    mock_cached_path = {
        "start_user": "0",
        "end_user": "150",
        "path": ["0", "107", "150"],
        "hops": 2,
        "cached": False,  # pathfinder sets this to True
    }

    with patch("app.services.pathfinder.redis_cache.get_cached_path", return_value=mock_cached_path):
        response = client.get("/api/v1/path/0/150")

    assert response.status_code == 200
    data = response.json()
    assert data["hops"] == 2
    assert data["path"] == ["0", "107", "150"]
    assert data["cached"] is True


def test_path_not_found_returns_404():
    """
    When no path exists between two users, the endpoint should return 404.
    """
    with patch("app.services.pathfinder.redis_cache.get_cached_path", return_value=None):
        with patch("app.services.pathfinder.graph_repo.find_shortest_path", return_value=None):
            response = client.get("/api/v1/path/0/9999")

    assert response.status_code == 404
