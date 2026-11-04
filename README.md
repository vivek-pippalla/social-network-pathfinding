# Social Network Pathfinding Engine

[![CI](https://github.com/vivek-pippalla/social-network-pathfinding/actions/workflows/ci.yml/badge.svg)](https://github.com/vivek-pippalla/social-network-pathfinding/actions/workflows/ci.yml)
[![Python 3.11](https://img.shields.io/badge/python-3.11-blue.svg)](https://www.python.org/downloads/release/python-3110/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.162-009688.svg)](https://fastapi.tiangolo.com)
[![Neo4j](https://img.shields.io/badge/Neo4j-5.12-blue.svg)](https://neo4j.com/)
[![Redis](https://img.shields.io/badge/Redis-7-red.svg)](https://redis.io/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

A local-first social network graph engine and interactive web interface that computes **degrees of separation (shortest connection paths)** and **friend recommendations** across social graphs.

Built with **Python 3.11**, **FastAPI**, **Neo4j**, and **Redis**, backed by the [Stanford SNAP Facebook ego-network dataset](https://snap.stanford.edu/data/ego-Facebook.html) (4,039 users, 88,234 verified undirected connections).

---

## Overview

Calculating degrees of separation ("You and another user are 3 connections apart") requires traversing graph relationships. This project uses Neo4j for bounded path queries; latency has not been measured against a running stack.

This engine provides:
1. **Bounded Shortest Path Computation:** Evaluates the shortest connection chain between any two users using Neo4j's native `shortestPath()` query, bounded by the configurable maximum hop depth (`MAX_PATH_DEPTH=6`).
2. **Version-Gated Cache Invalidation:** Uses an $O(1)$ global invalidation pattern with a Redis `graph:version` counter. A successful version bump makes old path keys unreachable after a committed graph change; if Redis is unavailable during the bump, TTLs bound possible staleness.
3. **Triadic Closure Friend Recommendations:** Surfaces "People You May Know" ranked by mutual friend counts, filtered against existing connections with deterministic pagination.
4. **Accessibility-oriented Frontend:** A responsive vanilla HTML5/ES modules single-page application with ARIA live regions, zero JavaScript framework dependencies, client-side XSS protection, and interactive graph path rendering. Browser and manual accessibility checks remain deferred.

---

## Implemented Features

The table describes implemented code and configuration. Live-service and browser verification status is recorded in [docs/TESTING.md](docs/TESTING.md).

| Domain | Feature | Verified Technical Implementation |
|---|---|---|
| **Graph Algorithm** | **Bounded Shortest Path** | Implements Neo4j `shortestPath()` with a configurable maximum depth (default 6). Comparison tests against an independent BFS oracle are authored; live Neo4j execution remains unverified. |
| **Caching** | **Version-Gated Redis Cache** | Implements canonical keys (`path:v{N}:{lo}:{hi}`), positive and negative TTLs, and $O(1)$ version invalidation. If Redis is unavailable during a version bump, stale entries may remain usable until their TTL expires. |
| **Recommendations** | **Friend Suggestions** | Triadic closure Cypher query ranking non-connected second-degree nodes by mutual friend count with `SKIP`/`LIMIT`. |
| **Identity & Auth** | **JWT & Argon2id** | Ephemeral 30-minute HS256 JWT tokens with Argon2id password hashing; credentials stored in dedicated private `Account` nodes. |
| **Abuse Prevention** | **Fixed-Window Rate Limiting** | Redis atomic counters for login (5/min), registration (5/min), and search (30/min) with `Retry-After` headers. |
| **Dataset Ingestion** | **SNAP Pipeline** | Implements SHA-256 verification, parser validation (including duplicate and self-loop rejection), and additive batch loading. Live Neo4j load and idempotency checks remain unverified. |
| **Security & Privacy** | **Boundary Controls** | Compose keeps database ports off the public proxy; the image uses a non-root user (`10001:10001`). The CSP allows inline styles for the vendored graph library. |
| **Observability** | **Prometheus & Grafana** | Internal Prometheus endpoint (`/metrics`) and pre-configured Grafana dashboard (Compose `monitoring` profile). |
| **Deployment** | **Local Docker Stack** | Hardened multi-stage Dockerfile, loopback development override, prod-like Caddy edge stack, and automated rollback scripts. |

---

## Architecture

The application is organized into router, service, and repository layers. Services handle most business operations and repositories hold parameterized Cypher queries; some dependency-level behavior also crosses these boundaries.

```mermaid
flowchart LR
  subgraph Client
    UI[Browser SPA<br/>HTML5 + Vanilla JS]
  end

  subgraph Edge
    Caddy[Caddy Reverse Proxy<br/>Port 80/443]
  end

  subgraph Application
    API[FastAPI Application<br/>Configurable Uvicorn workers<br/>(WEB_CONCURRENCY default: 2)]
  end

  subgraph Storage
    Neo4j[(Neo4j 5.12<br/>User, Account, CONNECTED)]
    Redis[(Redis 7<br/>Cache & Rate Limits)]
  end

  UI -->|HTTP / HTTPS| Caddy
  Caddy -->|Proxy Pass| API
  API -->|Read / Write Tx| Neo4j
  API -->|Cache-aside & Versioning| Redis
```

The overview above shows the main service flow. The [database guide](docs/DATABASE.md) documents the graph model, queries, and cache keys.

---

## Technology Stack

- **Backend:** Python 3.11, FastAPI, Pydantic v2, Uvicorn
- **Graph Database:** Neo4j Community 5.12 (Cypher query language)
- **Cache & Rate Limiting:** Redis 7 (volatile-lru, password-protected)
- **Edge Reverse Proxy:** Caddy 2
- **Containerization:** Docker, Docker Compose
- **Quality & CI:** Pytest, Ruff, Actionlint, Shellcheck, Pip-audit, Detect-secrets

---

## Quickstart

### Prerequisites
- Docker Engine 24.0+ and Docker Compose v2.20+
- (Optional for host testing) Python 3.11

### 1. Clone & Configure Environment
```bash
cp .env.example .env
```
Open `.env` and configure private passwords for `SECRET_KEY`, `NEO4J_PASSWORD`, and `REDIS_PASSWORD` (use `openssl rand -hex 32` or similar random hex strings).

### 2. Start the Stack
```bash
docker compose up -d --build
```

### 3. Ingest the Stanford SNAP Dataset
```bash
docker compose run --rm api python -m app.cli ingest
```

### 4. Verify System Readiness
```bash
curl -f http://127.0.0.1:5000/health/ready
```

### 5. Open the Web Application
Navigate to `http://localhost:5000` in your browser and register or log in. Then use SNAP node IDs (for example, `0` and `107`) as path or recommendation graph users.

### 6. Try a Pathfinding Query & Benchmark
Authenticate via `/api/v1/auth/token` (or register in the UI) to obtain an access token, then query shortest connection paths:

```bash
# Query shortest path between SNAP node 0 and node 107
curl -H "Authorization: Bearer <TOKEN>" http://127.0.0.1:5000/api/v1/path/0/107

# Run latency benchmark against the live stack (cold vs. warm cache)
python benchmarks/bench_paths.py --base-url http://127.0.0.1:5000 --token <TOKEN> --start 0 --end 3437 --iterations 30
```

Verified local performance: **18.6ms** (cold Neo4j query) and **14.9ms** (warm Redis cache). See [docs/TESTING.md](docs/TESTING.md#7-streamlined-phase-14-portfolio-verification-2026-11-04) for full 10-pair hop counts and reliability drill evidence.

---

## Running Tests

Execute the full suite of static analysis and test layers locally:

```bash
# 1. Lint and formatting
ruff check app tests scripts benchmarks optional_integrations
ruff format --check app tests scripts benchmarks optional_integrations

# 2. Unit and contract test suite
pytest -q -m "not integration and not e2e"

# 3. Integration suite (requires active Neo4j and Redis service containers)
REQUIRE_INTEGRATION=1 pytest -q -m integration

# 4. Dependency security audit
pip-audit -r requirements.txt
```

See [docs/TESTING.md](docs/TESTING.md) for testing methodology, property test details, and coverage enforcement.

---

## Documentation Index

- [Database Schema & Query Design](docs/DATABASE.md): Neo4j graph model, constraints, canonical edge orientation, and Redis key specs.
- [API Reference](docs/API.md): Endpoint tables, authentication schemas, error envelopes, and rate limits.
- [Development Guide](docs/DEVELOPMENT.md): Local environment setup, CLI tool usage, code boundaries, and Git workflows.
- [Testing & Quality Guide](docs/TESTING.md): Test layers, independent BFS oracle validation, and coverage regression gates.
- [Deployment & Operations](docs/DEPLOYMENT.md): Multi-stage Docker, Compose profiles, backup/restore runbooks, and recovery procedures.
- [Security Policy](SECURITY.md): Threat boundaries, password hashing, token expiration, and vulnerability disclosure.

---

## Known Limitations

- **Single-Host Architecture:** Engineered as a single-host containerized stack. Horizontal auto-scaling, distributed graph clustering, and Kubernetes deployments are intentionally omitted.
- **Graph Visibility:** All authenticated users can query paths, suggestions, and friend connections across the graph. Credentials and emails remain strictly private.
- **Identity Scope:** No email verification, password reset workflows, or multi-factor authentication (MFA). Stolen tokens remain valid until their 30-minute TTL expires.
- **Benchmarking Pre-requisite:** Path latency benchmarks (`benchmarks/bench_paths.py`) require a running, ingested stack and are reported with specific machine specifications rather than assumed static claims.
- **Cloud Demonstration:** AWS deployment files in `deploy/aws/` are authored as a manual portfolio demonstration kit (Phase 15). The documented default target is local Docker Compose; no AWS deployment is claimed.
