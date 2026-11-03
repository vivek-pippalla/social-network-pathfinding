import asyncio
import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.api.request_size import RequestBodyLimitMiddleware
from app.api.deps import get_current_user
from app.main import app
from scripts.export_openapi import API_PATH, render_api_markdown

OPENAPI_PATH = Path(__file__).resolve().parents[2] / "docs" / "openapi.json"
EXPECTED_ROUTES = {
    ("GET", "/health"),
    ("GET", "/health/ready"),
    ("POST", "/api/v1/auth/register"),
    ("POST", "/api/v1/auth/token"),
    ("GET", "/api/v1/users/me"),
    ("PUT", "/api/v1/users/me"),
    ("GET", "/api/v1/users/{id}"),
    ("GET", "/api/v1/users/search"),
    ("GET", "/api/v1/friends"),
    ("POST", "/api/v1/friends/{id}"),
    ("DELETE", "/api/v1/friends/{id}"),
    ("GET", "/api/v1/users/{id}/mutual"),
    ("GET", "/api/v1/path/{a}/{b}"),
    ("GET", "/api/v1/suggestions/me"),
    ("GET", "/api/v1/users/{id}/suggestions"),
}
PUBLIC_OPERATIONS = {
    ("GET", "/health"),
    ("GET", "/health/ready"),
    ("POST", "/api/v1/auth/register"),
    ("POST", "/api/v1/auth/token"),
}


def openapi():
    return app.openapi()


def test_openapi_route_inventory_and_operation_ids_match_plan():
    schema = openapi()
    routes = {
        (method.upper(), path)
        for path, operations in schema["paths"].items()
        for method in operations
        if method in {"get", "post", "put", "patch", "delete"}
    }
    operation_ids = [
        operation["operationId"]
        for operations in schema["paths"].values()
        for operation in operations.values()
        if "operationId" in operation
    ]

    assert routes == EXPECTED_ROUTES
    assert len(operation_ids) == len(set(operation_ids)) == len(EXPECTED_ROUTES)
    assert "securitySchemes" in schema["components"]
    for operations in schema["paths"].values():
        for operation in operations.values():
            assert operation["tags"]
            assert operation["summary"]
            assert operation["operationId"]
            success_response = next(
                response
                for code, response in operation["responses"].items()
                if code.startswith("2")
            )
            response_schema = success_response["content"]["application/json"]["schema"]
            component_name = response_schema["$ref"].rsplit("/", 1)[-1]
            assert schema["components"]["schemas"][component_name].get("examples")


def test_openapi_auth_requirements_match_route_contract():
    schema = openapi()
    for path, operations in schema["paths"].items():
        for method, operation in operations.items():
            if method not in {"get", "post", "put", "patch", "delete"}:
                continue
            expected_protected = (method.upper(), path) not in PUBLIC_OPERATIONS
            assert bool(operation.get("security")) is expected_protected


def test_every_documented_error_example_matches_the_error_envelope():
    schema = openapi()
    for operations in schema["paths"].values():
        for operation in operations.values():
            for response in operation["responses"].values():
                for code in response.get("x-error-codes", []):
                    examples = response["content"]["application/json"]["examples"]
                    envelope = examples[code]["value"]
                    assert envelope["error"]["code"] == code
                    assert set(envelope["error"]) == {
                        "code",
                        "message",
                        "request_id",
                        "details",
                    }


def _schema_properties(schema, components):
    if not isinstance(schema, dict):
        return set()
    if "$ref" in schema:
        name = schema["$ref"].rsplit("/", 1)[-1]
        return _schema_properties(components[name], components)
    found = set(schema.get("properties", {}))
    for child in schema.get("properties", {}).values():
        found |= _schema_properties(child, components)
    for child in (
        schema.get("items", {}).values()
        if isinstance(schema.get("items"), dict)
        else []
    ):
        found |= _schema_properties(child, components)
    for key in ("allOf", "anyOf", "oneOf"):
        for child in schema.get(key, []):
            found |= _schema_properties(child, components)
    return found


def test_only_own_profile_operations_document_email():
    schema = openapi()
    components = schema["components"]["schemas"]
    for path, operations in schema["paths"].items():
        for method, operation in operations.items():
            for response in operation["responses"].values():
                if not response.get("content"):
                    continue
                body_schema = response["content"]["application/json"].get("schema", {})
                properties = _schema_properties(body_schema, components)
                assert "password_hash" not in properties
                if "email" in properties:
                    assert (method.upper(), path) in {
                        ("GET", "/api/v1/users/me"),
                        ("PUT", "/api/v1/users/me"),
                    }


def test_openapi_snapshot_is_current():
    expected = (
        json.dumps(openapi(), indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    )
    assert OPENAPI_PATH.read_text(encoding="utf-8") == expected
    assert API_PATH.read_text(encoding="utf-8") == render_api_markdown(openapi())


def test_protected_route_matrix_rejects_requests_without_tokens():
    client = TestClient(app)
    substitutions = {"{id}": "contract-user", "{a}": "a", "{b}": "b"}
    for method, path in EXPECTED_ROUTES - PUBLIC_OPERATIONS:
        for placeholder, value in substitutions.items():
            path = path.replace(placeholder, value)
        response = getattr(client, method.lower())(path)
        assert response.status_code == 401, (method, path, response.text)
        assert response.json()["error"]["code"] == "UNAUTHENTICATED"


def test_metrics_is_bearer_protected_but_not_in_public_openapi():
    response = TestClient(app).get("/metrics")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHENTICATED"
    assert "/metrics" not in openapi()["paths"]


def test_metrics_is_available_after_bearer_authentication():
    previous = app.dependency_overrides.copy()
    app.dependency_overrides[get_current_user] = lambda: {"user_id": "monitor"}
    try:
        response = TestClient(app).get("/metrics")
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous)
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")


def test_request_bodies_over_the_configured_limit_use_error_envelope():
    too_large = b"x" * (app.state.settings.MAX_REQUEST_BODY_BYTES + 1)
    client = TestClient(app)
    response = client.post(
        "/api/v1/auth/register",
        content=too_large,
        headers={"Content-Type": "application/json", "X-Request-ID": "oversized-test"},
    )
    assert response.status_code == 413
    assert response.headers["x-request-id"] == "oversized-test"
    assert response.json()["error"] == {
        "code": "REQUEST_TOO_LARGE",
        "message": "The request body exceeds the configured limit.",
        "request_id": "oversized-test",
        "details": [],
    }

    malformed_id_response = client.post(
        "/api/v1/auth/register",
        content=too_large,
        headers={"Content-Type": "application/json", "X-Request-ID": "invalid id"},
    )
    assert malformed_id_response.status_code == 413
    assert (
        malformed_id_response.json()["error"]["request_id"]
        == (malformed_id_response.headers["x-request-id"])
    )


def test_chunked_request_bodies_cannot_bypass_the_size_limit():
    messages = iter(
        [
            {"type": "http.request", "body": b"1234", "more_body": True},
            {"type": "http.request", "body": b"5678", "more_body": False},
        ]
    )
    sent = []
    app_called = False

    async def receive():
        return next(messages)

    async def send(message):
        sent.append(message)

    async def downstream(_scope, _receive, _send):
        nonlocal app_called
        app_called = True

    middleware = RequestBodyLimitMiddleware(downstream, max_bytes=5)
    asyncio.run(
        middleware(
            {
                "type": "http",
                "method": "POST",
                "headers": [],
            },
            receive,
            send,
        )
    )

    assert app_called is False
    assert sent[0]["status"] == 413
    assert json.loads(sent[1]["body"])["error"]["code"] == "REQUEST_TOO_LARGE"
