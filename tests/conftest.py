import os
from unittest.mock import MagicMock

# Explicit non-production configuration for test collection and module imports.
os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("SECRET_KEY", "test-only-secret-key-32-bytes-minimum")
os.environ.setdefault("NEO4J_PASSWORD", "test-neo4j-password")
import pytest
from app.main import app
from app.db.neo4j_db import get_driver


@pytest.fixture(autouse=True)
def override_get_driver():
    """Replace the Neo4j driver dependency with a mock for every test.
    CI has no Neo4j instance, so get_driver() would fail on verify_connectivity()."""
    mock_driver = MagicMock()
    app.dependency_overrides[get_driver] = lambda: mock_driver
    yield mock_driver
    app.dependency_overrides.pop(get_driver, None)
