"""Export the reviewed OpenAPI schema and regenerate the API reference."""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.main import app  # noqa: E402


OPENAPI_PATH = ROOT / "docs" / "openapi.json"
API_PATH = ROOT / "docs" / "API.md"


def render_api_markdown(spec: dict) -> str:
    rows = []
    for path, operations in sorted(spec["paths"].items()):
        for method, operation in sorted(operations.items()):
            if method not in {"get", "post", "put", "patch", "delete"}:
                continue
            auth = "Bearer token" if operation.get("security") else "None"
            success = ", ".join(
                code
                for code in operation.get("responses", {})
                if code.isdigit() and 200 <= int(code) < 300
            )
            rows.append(
                f"| `{method.upper()}` | `{path}` | {auth} | "
                f"{operation.get('summary', '')} | {success or '—'} |"
            )

    return (
        """# API Reference

This endpoint table is generated from `docs/openapi.json` by
`python scripts/export_openapi.py`. The OpenAPI document is the route and schema
source of truth.

## Endpoints

| Method | Path | Authentication | Purpose | Success |
|---|---|---|---|---|
"""
        + "\n".join(rows)
        + """

## Authentication

Registration uses `POST /api/v1/auth/register` with JSON fields `name`, `email`,
and `password`. Login uses the OAuth2 password form at `POST /api/v1/auth/token`;
submit the email in the `username` field. Send the returned token as
`Authorization: Bearer <token>` to protected operations. Access tokens expire
after 30 minutes.

## Errors

Every non-success API response uses
`{ "error": { "code", "message", "request_id", "details" } }`. Validation
details contain locations and error types, never submitted values. Stable
application codes are `VALIDATION_ERROR`, `UNAUTHENTICATED`, `RATE_LIMITED`,
`EMAIL_TAKEN`, `USER_NOT_FOUND`, `PATH_NOT_FOUND`, `CANNOT_FRIEND_SELF`,
`UNAVAILABLE`, `INTERNAL`, and `REQUEST_TOO_LARGE`.

Request bodies are limited by `MAX_REQUEST_BODY_BYTES` (1 MiB by default).
Oversized bodies receive `413 REQUEST_TOO_LARGE` before route processing.

## Rate limits

Login allows five attempts per minute per IP and per IP/email pair. Registration
allows five attempts per minute per IP. User search allows 30 requests per
minute per IP. Rejections return `429 RATE_LIMITED` and a `Retry-After` header.
Login and registration return `503 UNAVAILABLE` if Redis cannot enforce their
limits; search continues if Redis is unavailable.

## Operational routes

`/metrics` is excluded from the public OpenAPI schema. The API allows only
loopback or private-network connection peers and ignores forwarded client-IP
headers. The development API port is bound to localhost, and Caddy returns 404
for `/metrics` before proxying public traffic. Other reverse proxies must also
deny this path instead of forwarding it. `/docs` and `/openapi.json` are
available only when `ENABLE_DOCS` is enabled. `GET /health` is liveness;
`GET /health/ready` checks Neo4j and reports Redis as `ok` or `degraded`.
"""
    )


def artifacts(spec: dict) -> dict[Path, str]:
    return {
        OPENAPI_PATH: json.dumps(spec, indent=2, sort_keys=True, ensure_ascii=False)
        + "\n",
        API_PATH: render_api_markdown(spec),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    generated = artifacts(app.openapi())
    if args.check:
        stale = [
            path.relative_to(ROOT)
            for path, content in generated.items()
            if not path.exists() or path.read_text(encoding="utf-8") != content
        ]
        if stale:
            print("Stale API artifacts: " + ", ".join(map(str, stale)), file=sys.stderr)
            return 1
        print("OpenAPI and API reference are current.")
        return 0

    for path, content in generated.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8", newline="\n")
        print(f"Wrote {path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
