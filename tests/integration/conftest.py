import os

import pytest
import redis
from neo4j import GraphDatabase
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.db.neo4j_db import get_driver
from app.db.redis_cache import get_client
from app.db.schema import ensure_schema


def _unavailable(request, service, error):
    message = f"Integration service {service} is unavailable: {error}"
    if os.getenv("REQUIRE_INTEGRATION") == "1":
        pytest.fail(message, pytrace=False)
    pytest.skip(message)


@pytest.fixture(scope="session")
def neo4j_driver(request):
    uri = os.getenv("TEST_NEO4J_URI", "bolt://127.0.0.1:17687")
    user = os.getenv("TEST_NEO4J_USER", "neo4j")
    password = os.getenv("TEST_NEO4J_PASSWORD", "integration-test-password")
    driver = GraphDatabase.driver(uri, auth=(user, password))
    try:
        driver.verify_connectivity()
    except Exception as exc:
        driver.close()
        _unavailable(request, "Neo4j", exc)
    yield driver
    driver.close()


@pytest.fixture(scope="session")
def redis_client(request):
    url = os.getenv("TEST_REDIS_URL", "redis://127.0.0.1:16379/15")
    client = redis.Redis.from_url(url, decode_responses=True, socket_timeout=1)
    try:
        client.ping()
    except Exception as exc:
        client.close()
        _unavailable(request, "Redis", exc)
    yield client
    client.close()


@pytest.fixture
def clean_graph(neo4j_driver, redis_client):
    """Clean only the dedicated test services, then provision their schema."""
    with neo4j_driver.session() as session:
        session.execute_write(lambda tx: tx.run("MATCH (n) DETACH DELETE n").consume())
    ensure_schema(neo4j_driver)
    redis_client.flushdb()
    yield neo4j_driver, redis_client


@pytest.fixture
def api_client(clean_graph):
    """Build an API instance wired to the real, isolated integration services."""
    driver, redis_client = clean_graph
    from app.main import create_app

    application = create_app(
        get_settings().model_copy(update={"AUTO_SCHEMA": False}),
        driver_provider=lambda: driver,
        redis_provider=lambda: redis_client,
        driver_closer=lambda: None,
    )
    application.dependency_overrides[get_driver] = lambda: driver
    application.dependency_overrides[get_client] = lambda: redis_client
    with TestClient(application) as client:
        yield client
    application.dependency_overrides.clear()
