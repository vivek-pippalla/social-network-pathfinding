# Security Policy

This document details the threat model, security controls, cryptographic standards, data isolation boundaries, known limitations, and vulnerability reporting procedures for the Social Network Pathfinding Engine.

---

## 1. Authentication & Account Security

- **Credential Isolation:** Passwords and email addresses are stored exclusively in dedicated private `(:Account)` nodes, separate from public `(:User)` profile nodes. Public user profile queries, graph searches, and recommendation algorithms have no structural access to credential properties.
- **Password Storage:** Passwords are hashed using **Argon2id** (`argon2-cffi`) with pinned memory, time, and parallelism parameters. Plaintext passwords are never logged, cached, or persisted.
- **Timing-Attack Mitigation:** Login attempts for non-existent email addresses verify the submitted password against a precomputed dummy Argon2id hash (cached via `@lru_cache`) before returning `401 UNAUTHENTICATED`. This performs a password-hash operation on both paths to reduce timing differences; it does not promise perfectly constant response time.
- **Input Validation:** User registration strictly validates email format (`EmailStr`), display name length (1 to 100 characters), and password complexity (10 to 128 characters, distinct from name and email).

---

## 2. Session Management & Tokens

- **Ephemeral Access Tokens:** Tokens use JSON Web Tokens (JWT) signed with **HS256** via `PyJWT`. The signing algorithm is pinned to prevent algorithm-confusion attacks (e.g. `none` algorithm exploits).
- **Token Claims:** Every token carries standard claims: `sub` (user ID), `iat` (issued-at UTC timestamp), and `exp` (expiration UTC timestamp).
- **Short Lifespan:** Access tokens are strictly time-bounded to 30 minutes (`ACCESS_TOKEN_EXPIRE_MINUTES=30`).
- **Subject Verification:** A valid cryptographic signature is immediately invalidated if the user specified in the `sub` claim has been removed from the graph.

---

## 3. Rate Limiting & Abuse Prevention

The system enforces atomic fixed-window rate limits in Redis:

| Route | Scope | Limit | Failure Mode |
|---|---|---|---|
| `POST /api/v1/auth/token` | Client IP | 5 requests / minute | **Fails Closed** (503 UNAVAILABLE) |
| `POST /api/v1/auth/token` | Client IP + Target Email | 5 requests / minute | **Fails Closed** (503 UNAVAILABLE) |
| `POST /api/v1/auth/register` | Client IP | 5 requests / minute | **Fails Closed** (503 UNAVAILABLE) |
| `GET /api/v1/users/search` | Client IP | 30 requests / minute | **Fails Open** (Search proceeds) |

When a rate limit is exceeded, the API returns HTTP `429 RATE_LIMITED` with a `Retry-After` header indicating the seconds remaining until the window resets.

---

## 4. Graph Injection & Boundary Defense

- **Parameterized Cypher:** All queries executed against Neo4j use parameterized values exclusively (`$param`). String interpolation or user input concatenation into Cypher statements is prohibited.
- **Path Depth Boundaries:** Cypher shortest-path queries interpolate an integer literal depth bound derived strictly from server settings (`MAX_PATH_DEPTH=6`), preventing unbound graph traversal denial-of-service attacks.
- **Path Parameter Regex:** Path parameters (`{a}`, `{b}`, `{id}`) are constrained by strict alphanumeric regex filters (`^[A-Za-z0-9_-]{1,64}$`), preventing injection or parameter reflection in error messages.
- **Error Envelope Hygiene:** Application errors return a standardized JSON structure (`{ "error": { "code", "message", "request_id", "details" } }`). Validation error details expose field names and error types, never reflecting raw submitted input strings.

---

## 5. Network & Infrastructure Security

- **Reverse Proxy Protection:** In production (`docker-compose.prod.yml`), Caddy terminates edge traffic and strips public access to internal ports. Neo4j (7474, 7687) and Redis (6379) ports are unexposed to the host network.
- **Metrics Access Isolation:** The Prometheus metrics endpoint (`/metrics`) is restricted to loopback and private network peers. Caddy explicitly responds with HTTP 404 for `/metrics` before forwarding public traffic.
- **Client IP Trust Boundaries:** The API does not blindly trust `X-Forwarded-For` headers. Uvicorn only accepts forwarded headers from explicitly configured IP addresses (`TRUSTED_PROXY_ADDRESSES`).
- **Container Hardening:** The API container runs under a non-root system user (`USER 10001:10001`). Note that container root filesystems are not mounted read-only (`read_only: true` is not set in Compose).
- **XSS Prevention:** The single-page frontend avoids dynamic HTML construction via `innerHTML`, relying exclusively on safe DOM population via `textContent`. FastAPI sets a Content Security Policy with `default-src 'self'`; `style-src` permits inline styles for the vendored vis-network renderer. The policy is set by application middleware (`app/main.py`), not by the reverse proxy.

---

## 6. Known Security Limitations

The following capabilities are deliberately out of scope for this personal single-host architecture:

1. **Email Verification:** Registration does not require out-of-band email verification.
2. **Password Reset:** Self-service password reset and account recovery flows are not implemented.
3. **Multi-Factor Authentication (MFA):** Authentication is single-factor (email and password).
4. **Token Revocation:** Tokens cannot be revoked prior to their 30-minute expiration. Stolen tokens remain active until expiration.
5. **Authenticated Graph Visibility:** Any authenticated user can view degrees of separation and connection graphs between any two users in the system.

---

## 7. Reporting a Vulnerability

If you discover a security vulnerability within this project, please report it privately:

1. **Do Not Open a Public Issue:** Never disclose potential security flaws publicly in GitHub Issues or Discussions.
2. **Contact:** Email the repository maintainer directly with details and reproduction steps.
3. **Safe Demonstration:** Include a concise proof-of-concept using synthetic data. Never include production secrets, database credentials, or real user tokens in vulnerability reports.
