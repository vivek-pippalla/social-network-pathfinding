# API Reference

This endpoint table is generated from `docs/openapi.json` by
`python scripts/export_openapi.py`. The OpenAPI document is the route and schema
source of truth.

## Endpoints

| Method | Path | Authentication | Purpose | Success |
|---|---|---|---|---|
| `POST` | `/api/v1/auth/register` | None | Register a new user account | 201 |
| `POST` | `/api/v1/auth/token` | None | Login and get a JWT token | 200 |
| `GET` | `/api/v1/friends` | Bearer token | List your friends | 200 |
| `DELETE` | `/api/v1/friends/{id}` | Bearer token | Remove yourself as a friend | 200 |
| `POST` | `/api/v1/friends/{id}` | Bearer token | Add yourself as a friend | 201, 200 |
| `GET` | `/api/v1/path/{a}/{b}` | Bearer token | Shortest path between two users (protected) | 200 |
| `GET` | `/api/v1/suggestions/me` | Bearer token | Get your own friend suggestions (protected) | 200 |
| `GET` | `/api/v1/users/me` | Bearer token | Get your own profile | 200 |
| `PUT` | `/api/v1/users/me` | Bearer token | Update your name | 200 |
| `GET` | `/api/v1/users/search` | Bearer token | Search users by name | 200 |
| `GET` | `/api/v1/users/{id}` | Bearer token | Get public user profile | 200 |
| `GET` | `/api/v1/users/{id}/mutual` | Bearer token | List mutual friends | 200 |
| `GET` | `/api/v1/users/{id}/suggestions` | Bearer token | Get friend suggestions for a user (protected) | 200 |
| `GET` | `/health` | None | Liveness check | 200 |
| `GET` | `/health/ready` | None | Dependency readiness check | 200 |

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
