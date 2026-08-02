from unittest.mock import MagicMock
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
