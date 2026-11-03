import json
import logging
import os
import subprocess
import sys

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from neo4j.exceptions import ServiceUnavailable, SessionExpired
from pydantic import ValidationError

from app.core.config import Settings
from app.core.logging import JSONFormatter
from app.main import create_app
from app.domain.errors import AppError

TEST_SECRET = "test-only-secret-key-32-bytes-minimum"


def make_settings(**overrides):
    values = {
        "_env_file": None,
        "APP_ENV": "test",
        "SECRET_KEY": TEST_SECRET,
        "NEO4J_PASSWORD": "unit-test-neo4j-password",
        "AUTO_SCHEMA": False,
    }
    values.update(overrides)
    return Settings(**values)


@pytest.mark.parametrize(
    "value",
    [
        None,
        "short",
        "your-secret-key-here-use-openssl-rand-hex-32",
        "replace-with-at-least-32-random-characters",
    ],
)
def test_settings_reject_missing_short_and_placeholder_secret(value, monkeypatch):
    monkeypatch.delenv("SECRET_KEY", raising=False)
    monkeypatch.delenv("NEO4J_PASSWORD", raising=False)
    arguments = {
        "_env_file": None,
        "APP_ENV": "test",
        "NEO4J_PASSWORD": "valid-neo4j-password",
    }
    if value is not None:
        arguments["SECRET_KEY"] = value
    with pytest.raises(ValidationError):
        Settings(**arguments)


def test_application_import_refuses_to_start_without_required_secret(monkeypatch):
    monkeypatch.delenv("SECRET_KEY", raising=False)
    environment = os.environ.copy()
    environment.pop("SECRET_KEY", None)
    environment["APP_ENV"] = "dev"
    result = subprocess.run(
        [sys.executable, "-c", "import app.main"],
        cwd=os.getcwd(),
        env=environment,
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert result.returncode != 0
    assert "SECRET_KEY" in result.stderr


def test_env_example_secret_values_are_non_passing_placeholders():
    from dotenv import dotenv_values

    example = dotenv_values(".env.example")
    with pytest.raises(ValidationError):
        make_settings(SECRET_KEY=example["SECRET_KEY"])
    with pytest.raises(ValidationError):
        make_settings(NEO4J_PASSWORD=example["NEO4J_PASSWORD"])


def test_test_environment_accepts_explicit_secret_from_environment(monkeypatch):
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("SECRET_KEY", TEST_SECRET)
    monkeypatch.setenv("NEO4J_PASSWORD", "valid-neo4j-password")
    assert Settings(_env_file=None).SECRET_KEY == TEST_SECRET


def test_explicit_test_secret_is_rejected_outside_test_environment():
    with pytest.raises(ValidationError):
        make_settings(APP_ENV="prod")


@pytest.mark.parametrize(
    "value",
    ["", "short", "your-neo4j-password-here", "replace-with-a-private-password"],
)
def test_settings_reject_missing_short_and_placeholder_neo4j_password(
    value, monkeypatch
):
    monkeypatch.delenv("NEO4J_PASSWORD", raising=False)
    arguments = {"_env_file": None, "APP_ENV": "test", "SECRET_KEY": TEST_SECRET}
    if value or value == "":
        arguments["NEO4J_PASSWORD"] = value
    with pytest.raises(ValidationError):
        Settings(**arguments)


def test_settings_phase_defaults_and_cached_accessor():
    from app.core.config import get_settings

    config = make_settings()
    assert (config.MAX_PATH_DEPTH, config.NEO4J_QUERY_TIMEOUT_SECONDS) == (6, 5)
    assert config.REDIS_SOCKET_TIMEOUT_SECONDS == 0.2
    assert (config.CACHE_TTL_SECONDS, config.NEGATIVE_CACHE_TTL_SECONDS) == (300, 60)
    assert config.ACCESS_TOKEN_EXPIRE_MINUTES == 30
    assert get_settings() is get_settings()


def make_app(*, config=None, driver=None, redis=None):
    driver = driver or type("Driver", (), {"verify_connectivity": lambda self: None})()
    redis = redis or type("Redis", (), {"ping": lambda self: True})()
    return create_app(
        config or make_settings(),
        driver_provider=lambda: driver,
        redis_provider=lambda: redis,
        driver_closer=lambda: None,
    )


def test_uniform_error_envelope_and_validation_does_not_echo_input():
    app = make_app()

    @app.get("/test/{number}")
    async def typed(number: int):
        return {"number": number}

    @app.get("/raise-http")
    async def raise_http():
        raise HTTPException(401, detail="sensitive supplied value")

    @app.get("/raise-domain")
    async def raise_domain():
        raise AppError("PATH_NOT_FOUND", "No path exists.", 404)

    with TestClient(app) as client:
        response = client.get("/test/not-a-number")
        assert response.status_code == 422
        body = response.json()
        assert body["error"]["code"] == "VALIDATION_ERROR"
        assert "not-a-number" not in response.text
        assert body["error"]["request_id"] == response.headers["X-Request-ID"]
        unauthorized = client.get("/raise-http")
        assert unauthorized.status_code == 401
        assert unauthorized.json()["error"]["code"] == "UNAUTHENTICATED"
        assert "sensitive supplied value" not in unauthorized.text
        domain_error = client.get("/raise-domain")
        assert domain_error.status_code == 404
        assert domain_error.json()["error"]["code"] == "PATH_NOT_FOUND"
        missing = client.get("/missing")
        assert missing.status_code == 404
        assert missing.json()["error"]["code"] == "NOT_FOUND"
        wrong_method = client.post("/test/1")
        assert wrong_method.status_code == 405
        assert wrong_method.json()["error"]["code"] == "METHOD_NOT_ALLOWED"


@pytest.mark.parametrize(
    "exception", [ServiceUnavailable("offline"), SessionExpired("expired")]
)
def test_neo4j_errors_return_unavailable_envelope(exception):
    app = make_app()

    @app.get("/neo4j-error")
    async def failing_route():
        raise exception

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/neo4j-error")
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "UNAVAILABLE"
    assert "offline" not in response.text and "expired" not in response.text


def test_unhandled_error_is_sanitized():
    app = make_app()

    @app.get("/explode")
    async def explode():
        raise RuntimeError("secret-password-value")

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/explode")
    assert response.status_code == 500
    assert response.json()["error"]["code"] == "INTERNAL"
    assert "secret-password-value" not in response.text


def test_request_id_validation_and_single_access_log(caplog):
    app = make_app()

    @app.post("/sensitive")
    async def sensitive_payload(payload: dict):
        return {"ok": bool(payload)}

    caplog.set_level(logging.INFO)
    with TestClient(app) as client:
        accepted = client.get("/health", headers={"X-Request-ID": "trace-123"})
        rejected = client.get("/health", headers={"X-Request-ID": "bad\r\nid"})
        client.post(
            "/sensitive",
            json={"password": "request-password-value"},
            headers={"Authorization": "Bearer request-token-value"},
        )
    assert accepted.headers["X-Request-ID"] == "trace-123"
    assert rejected.headers["X-Request-ID"] != "bad\r\nid"
    access_records = [
        record
        for record in caplog.records
        if record.name == "app.access" and record.getMessage() == "http_request"
    ]
    assert len(access_records) == 3
    assert access_records[0].route == "/health"
    assert access_records[0].request_id == "trace-123"
    assert all("Authorization" not in record.__dict__ for record in access_records)
    formatted = " ".join(JSONFormatter().format(record) for record in access_records)
    assert "request-password-value" not in formatted
    assert "request-token-value" not in formatted


def test_json_formatter_includes_request_context_without_sensitive_headers(caplog):
    record = logging.LogRecord(
        "app.access", logging.INFO, __file__, 1, "http_request", (), None
    )
    record.request_id = "safe-id"
    record.method = "GET"
    record.route = "/health"
    record.status = 200
    record.duration_ms = 1.25
    payload = json.loads(JSONFormatter().format(record))
    assert payload["request_id"] == "safe-id"
    assert payload["route"] == "/health"
    assert "Authorization" not in payload


def test_liveness_has_no_dependency_access_and_readiness_dependency_status():
    calls = []
    app = create_app(
        make_settings(),
        driver_provider=lambda: calls.append("driver"),
        redis_provider=lambda: calls.append("redis"),
        driver_closer=lambda: None,
    )
    with TestClient(app) as client:
        assert client.get("/health").status_code == 200
    assert calls == [
        "driver"
    ]  # Lifespan verifies startup; liveness itself adds no calls.

    class Driver:
        def verify_connectivity(self):
            return None

    class DownRedis:
        def ping(self):
            raise OSError("redis password omitted")

    app = make_app(driver=Driver(), redis=DownRedis())
    with TestClient(app) as client:
        assert client.get("/health").status_code == 200
        ready = client.get("/health/ready")
    assert ready.status_code == 200
    assert ready.json()["components"] == {"neo4j": "ok", "redis": "degraded"}

    class DownNeo4j:
        def verify_connectivity(self):
            raise ServiceUnavailable("private connection details")

    app = make_app(driver=DownNeo4j())
    with TestClient(app) as client:
        assert client.get("/health").status_code == 200
        failed = client.get("/health/ready")
    assert failed.status_code == 503
    assert failed.json()["error"]["code"] == "UNAVAILABLE"
    assert "private connection details" not in failed.text


def test_lifespan_bootstraps_schema_only_when_enabled():
    calls = []
    driver = object()
    app = create_app(
        make_settings(AUTO_SCHEMA=True),
        driver_provider=lambda: driver,
        redis_provider=lambda: None,
        driver_closer=lambda: None,
        schema_bootstrapper=lambda actual_driver: calls.append(actual_driver),
    )
    with TestClient(app):
        pass
    assert calls == [driver]

    calls.clear()
    disabled = create_app(
        make_settings(AUTO_SCHEMA=False),
        driver_provider=lambda: driver,
        redis_provider=lambda: None,
        driver_closer=lambda: None,
        schema_bootstrapper=lambda actual_driver: calls.append(actual_driver),
    )
    with TestClient(disabled):
        pass
    assert calls == []


def test_docs_and_cors_toggles():
    disabled = make_app(config=make_settings(ENABLE_DOCS=False, ALLOWED_ORIGINS=[]))
    with TestClient(disabled) as client:
        assert client.get("/docs").status_code == 404
        assert client.get("/openapi.json").status_code == 404
        assert "access-control-allow-origin" not in client.get("/health").headers

    enabled = make_app(
        config=make_settings(
            ENABLE_DOCS=True, ALLOWED_ORIGINS=["https://client.example"]
        )
    )
    with TestClient(enabled) as client:
        assert client.get("/openapi.json").status_code == 200
        cors = client.options(
            "/health",
            headers={
                "Origin": "https://client.example",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert cors.headers["access-control-allow-origin"] == "https://client.example"


def test_openapi_description_does_not_advertise_missing_routes():
    schema = make_app().openapi()
    assert "production-grade" not in schema["info"]["description"].lower()
    assert "/distance" not in schema["info"]["description"]
    assert "/profile/" not in schema["info"]["description"]
