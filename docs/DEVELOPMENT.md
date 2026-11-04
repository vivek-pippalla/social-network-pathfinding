# Development Guide

This guide covers local environment setup, configuration options, code layering standards, CLI utilities, testing workflows, and CI requirements for developers contributing to the project.

---

## 1. Local Environment Setup

### 1.1 Prerequisites
- **Python:** 3.11+
- **Docker & Docker Compose:** Docker Engine 24.0+ / Compose v2.20+
- **Git:** 2.30+

### 1.2 Virtual Environment & Dependencies
Create and activate an isolated virtual environment:

```bash
# Create virtual environment
python -m venv .venv

# Activate on Linux/macOS:
source .venv/bin/activate
# Activate on Windows (PowerShell):
# .venv\Scripts\Activate.ps1

# Upgrade pip and install runtime + development dependencies
python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt
```

---

## 2. Configuration & Secrets Management

The application reads configuration parameters from environment variables (or a local `.env` file) parsed by `app/core/config.py`.

### 2.1 Initialization
Copy the template to `.env`:
```bash
cp .env.example .env
```

### 2.2 Generating Secure Passwords
Generate strong random strings for required parameters:

```bash
# Linux / macOS / Git Bash
openssl rand -hex 32  # Use for SECRET_KEY
openssl rand -hex 24  # Use for NEO4J_PASSWORD
openssl rand -hex 24  # Use for REDIS_PASSWORD
```

### 2.3 Key Configuration Reference

| Variable | Default / Example | Purpose |
|---|---|---|
| `APP_ENV` | `dev` | Application mode (`dev`, `test`, `prod`). |
| `SECRET_KEY` | *(Required)* | 32+ character key for HS256 JWT signatures. |
| `NEO4J_URI` | `bolt://127.0.0.1:7687` | Bolt connection string for Neo4j. |
| `NEO4J_USER` | `neo4j` | Database username. |
| `NEO4J_PASSWORD` | *(Required)* | Database password (rejects placeholder strings). |
| `REDIS_URL` | `redis://127.0.0.1:6379/0` | Redis connection URL. |
| `REDIS_PASSWORD` | *(Required)* | Redis authentication password. |
| `MAX_PATH_DEPTH` | `6` | Upper bound for shortest path Cypher query depth. |
| `CACHE_TTL_SECONDS` | `300` | Expiration time for cached paths (5 minutes). |
| `NEGATIVE_CACHE_TTL_SECONDS` | `60` | Expiration time for unreachable path results. |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `30` | JWT token validity window. |
| `ENABLE_DOCS` | `true` | Toggle for `/docs` Swagger UI and `/openapi.json`. |
| `AUTO_SCHEMA` | `true` | Apply database constraints on startup. |

---

## 3. Application CLI Utilities

The CLI (`python -m app.cli`) provides essential maintenance and data lifecycle tools:

```bash
# 1. Apply schema constraints and indexes to Neo4j
python -m app.cli schema

# 2. Ingest the Stanford SNAP Facebook dataset (additive, idempotent)
python -m app.cli ingest

# 3. Invalidate all cached path results in Redis
python -m app.cli reset-cache

# 4. Generate a disposable test user for demo purposes
python -m app.cli demo-user
```

---

## 4. Code Standards & Architecture Boundaries

Maintain the three-tier layer architecture across all contributions:

```
app/
├── api/             # Routers: Request validation, dependency injection, response models
├── core/            # Config, security, exceptions, logging middleware
├── db/              # Neo4j driver, Redis client, schema initialization
├── models/          # Pydantic schemas, DTOs, API error contracts
├── repositories/    # Cypher queries, explicit read/write transactions
└── services/        # Business logic, authorization, cache orchestration
```

### Mandatory Rules
1. **Router Separation:** Routers parse HTTP requests and return Pydantic responses. Routers never query the database or Redis directly.
2. **Service Ownership:** All business logic (e.g. self-friendship rejection, path cache coordination) resides in `app/services/`. Services never touch FastAPI request objects.
3. **Repository Purity:** All Cypher queries reside in `app/repositories/`. Every query must be parameterized. String concatenation in Cypher queries is strictly prohibited.
4. **Credential Isolation:** Credentials (`Account`) must never be combined with public profiles (`User`).

---

## 5. Developer Quality Gates

Run all quality checks before submitting a pull request:

```bash
# 1. Code linting and formatting
ruff check app tests scripts benchmarks optional_integrations
ruff format --check app tests scripts benchmarks optional_integrations

# 2. Markdown documentation link check (local links & anchors)
python scripts/check_doc_links.py

# 3. OpenAPI contract and documentation freshness
python scripts/export_openapi.py --check

# 4. Unit and contract test suite
pytest -q -m "not integration and not e2e"

# 5. Service & repository coverage baseline regression check
pytest -q -m "not integration and not e2e" \
  --cov=app.services --cov=app.repositories \
  --cov-report=json:coverage.json
python scripts/check_coverage_baseline.py coverage.json .github/coverage-baseline.json

# 6. Dependency vulnerability audit
pip-audit -r requirements.txt

# 7. Git secret scanning
git ls-files -z | xargs -0 detect-secrets-hook --baseline .secrets.baseline
```

---

## 6. Branch Protection & CI Configuration

All pull requests targeting `main` must pass the automated GitHub Actions pipeline.

### Required Checks on `main`
Configure GitHub repository branch protection rules to require these 7 status checks:
1. `lint` (Ruff, Actionlint, Shellcheck, link check)
2. `unit` (Pytest unit suite + coverage baseline regression gate)
3. `integration` (Real Neo4j and Redis service containers; `REQUIRE_INTEGRATION=1`)
4. `contract` (OpenAPI freshness and UI-route agreement)
5. `e2e` (Compose stack bring-up, readiness probe, Playwright smoke journey)
6. `security` (Pip-audit runtime CVE check, Detect-secrets baseline check)
7. `image` (Docker image build without push)

The optional AWS release packaging workflow (`deploy-aws.yml`) is manual dispatch only and must not be configured as a required gate.
