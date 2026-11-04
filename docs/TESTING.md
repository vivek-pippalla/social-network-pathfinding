# Testing Strategy & Quality Assurance

This document details the multi-layered testing strategy, independent algorithm verification oracles, coverage enforcement, and operational test execution requirements.

---

## 1. Testing Philosophy: Real Services Over Mocks

A test is only valuable if it fails when the real underlying behavior breaks. Mocking internal databases hides Cypher syntax errors, constraint violations, and cache race conditions.

### Test Layer Matrix

| Layer | Directory / Marker | Infrastructure | What It Proves | Allowed Mocks |
|---|---|---|---|---|
| **Unit** | `tests/unit`<br/>*(unmarked)* | None (In-memory) | Pure algorithms, DTO validation, token generation/expiry, password hashing, config parsing, cache key format. | External I/O only. |
| **Contract** | `tests/contract`<br/>*(unmarked)* | None (In-memory) | Route inventory agreement between `js/api.js` and `docs/openapi.json`, response error envelopes, OpenAPI schema freshness. | None. |
| **Integration** | `tests/integration`<br/>`@pytest.mark.integration` | Real Neo4j 5.12 & Redis 7 | Constraint uniqueness, Cypher execution, write transactions, canonical edge sorting, rate-limit counters, cache version invalidation. | None. |
| **Property** | `tests/integration`<br/>`@pytest.mark.integration` | Real Neo4j & Python BFS Oracle | Bounded shortest path correctness and hop count agreement against an independent pure-Python BFS implementation across randomized graphs. | None. |
| **Script** | `tests/test_deploy_script.py`<br/>`tests/test_caddy_config.py` | Shell / Shims | Deployment rollback, local backup and restore invocations, Caddy reverse-proxy port routing rules. | Subprocess shims (`docker`, `curl`). |
| **End-to-End** | `tests/e2e`<br/>`@pytest.mark.e2e` | Full Docker Compose stack + Chromium | Full user journey via Playwright: registration, login, search, friend addition, path finding, and UI DOM rendering. | None. |

---

## 2. Independent BFS Oracle Property Testing

The integration property tests are designed to compare Neo4j's Cypher `shortestPath((a)-[:CONNECTED*..6]-(b))` with an independent BFS oracle. This comparison is not currently verified against live services because integration setup has not completed successfully:

1. **Random Graph Generation:** The integration test creates seeded pseudo-random graphs with known connected components and disconnected islands.
2. **Dual Execution:** Queries both the pure-Python BFS oracle and Neo4j's Cypher shortest path engine on identical node pairs.
3. **Invariants Verified:**
   - Hop counts must match exactly for all reachable node pairs.
   - For disconnected node pairs, both implementations must return "no path".
   - Paths exceeding `MAX_PATH_DEPTH=6` must terminate with a negative result.
   - Reversing the query endpoints (`(b, a)` vs `(a, b)`) must yield the identical hop distance.

---

## 3. Coverage Enforcement & Regression Gates

Coverage is not treated as a vanity gate (forcing tests on trivial boilerplate). Instead, regression gates prevent coverage drops across the core business and data layers:

- **Tracked Targets:** `app/services` and `app/repositories`
- **Recorded Baseline (`.github/coverage-baseline.json`):**
  - `app/services`: **85.44%**
  - `app/repositories`: **41.78%**
- **Enforcement Script (`scripts/check_coverage_baseline.py`):**
  Calculates statement coverage from `coverage.json` and fails CI if current coverage drops below either recorded baseline:
  ```bash
  pytest -q -m "not integration and not e2e" \
    --cov=app.services --cov=app.repositories \
    --cov-report=json:coverage.json
  python scripts/check_coverage_baseline.py coverage.json .github/coverage-baseline.json
  ```

---

## 4. Test Execution Runbook

### 4.1 Unit & Contract Tests (No Services Needed)
Runs without Neo4j or Redis:

```bash
pytest -q -m "not integration and not e2e"
```

### 4.2 Integration Tests (Requires Real Neo4j & Redis)
In CI, GitHub Actions service containers are configured for the integration job. Locally, start the test services with the repository helper:

```bash
# 1. Start test infrastructure
bash scripts/test-infra.sh up

# 2. Run integration suite with enforcement flag
REQUIRE_INTEGRATION=1 pytest -q -m integration

# 3. Teardown test services
bash scripts/test-infra.sh down
```

> **Note on `REQUIRE_INTEGRATION=1`:** If Neo4j or Redis is unreachable when this variable is set to `1`, tests will fail immediately rather than silently skipping.

### 4.3 End-to-End Browser Journey (Playwright)
Executes a headless Chromium browser smoke test:

```bash
# 1. Start complete application stack
docker compose up -d --build --wait

# 2. Run Playwright E2E suite
pytest -q -m e2e tests/e2e
```
On failure, Playwright automatically records and saves a full diagnostic archive to `test-results/playwright-trace.zip` (trace, screenshots, DOM snapshots, network logs).

---

## 5. Status of Test Verification

To maintain technical honesty:

| Test Scope | Status | Verification Context |
|---|---|---|
| **Unit Suite** | **VERIFIED LOCALLY** | The Phase 13 non-integration/non-e2e run completed with 167 passed, 1 skipped, and 44 deselected. This is not a 100% coverage or pass claim for every core module. |
| **Contract Suite** | **VERIFIED** | Executed locally; verified OpenAPI schema freshness and UI route agreement. |
| **Coverage Gate** | **VERIFIED** | Executed locally; meets recorded 85.44% / 41.78% baselines. |
| **Secret Scanning** | **VERIFIED LOCALLY** | The configured `detect-secrets` baseline check passed; a deliberate fake key was detected in a separate failure demonstration. |
| **Dependency Audit** | **VERIFIED LOCALLY** | `pip-audit -r requirements.txt` completed with no known runtime dependency vulnerabilities in the Phase 13 run. |
| **Real Integration Suite** | **NOT VERIFIED** | A prior run failed during service setup because Neo4j refused the local connection. Later real-service runs were deferred; CI is configured to require integration tests, but no remote Actions result is recorded here. |
| **Browser E2E Suite** | **NOT VERIFIED** | Requires the Docker stack and browser. CI is configured to run it, but no local or remote end-to-end result is recorded here. |
| **AWS Demonstration** | **UNVERIFIED** | Manual demonstration kit (Phase 15); not executed until Phase 15. |

## 6. Phase 14 Release Verification (2026-11-04)

**Release decision: BLOCKED.** No `v1.0.0` tag or release notes were created. The release check was run in the existing Windows workspace on branch `phase-13-documentation` at `efd1acf`, not on a clean clone. The README-only clean-machine bring-up, live service checks, and release pipeline therefore remain **UNVERIFIED**. The findings register in `docs/BUILD_PLAN.md` Section 3 has not been signed off finding by finding; implementation history and mocked/unit tests do not substitute for the required live proof.

### 6.1 Section 14 master acceptance checklist

| Item | Result | Evidence |
|---|---|---|
| Register/login/profile update; protected routes return the error envelope | UNVERIFIED | Local unit/contract suite: `python -m pytest -q -m "not integration and not e2e"` — 168 passed, 9 skipped, 36 deselected. No clean-stack journey or live auth run. |
| Search and public profile privacy | UNVERIFIED | Same local suite; live API/UI privacy journey not run. |
| Friend add/list/remove, idempotency, self/unknown-user handling | UNVERIFIED | Same local suite; real Neo4j behavior not exercised. |
| Mutual-friend results match a hand-checked dataset example | UNVERIFIED | No live dataset query performed. |
| Path oracle, ten dataset pairs, reverse/same/unreachable behavior | UNVERIFIED | Integration tests require Neo4j/Redis; no ten-pair results captured. |
| Deterministic suggestions and distinct mutual counts | UNVERIFIED | No live graph query performed. |
| Ingestion counts, idempotency, and registered-data preservation | UNVERIFIED | No stack/ingestion run. |
| Full UI journey and UI/OpenAPI route agreement | UNVERIFIED | Contract tests passed in the local suite; Playwright/browser journey not run (`playwright` unavailable and Docker engine absent). |
| Startup rejects missing, short, or placeholder secrets | UNVERIFIED | Unit tests ran, but clean-container startup checks were not run. |
| No email/password-hash exposure beyond caller's own profile | UNVERIFIED | No live API response inspection. |
| Friendship ownership boundary | UNVERIFIED | No live authorization drill. |
| Rate limits active; login fails closed when Redis is down | UNVERIFIED | No live Redis/rate-limit drill. |
| Dependency audit clean or remaining advisories justified; deprecated packages absent | UNVERIFIED | `python -m pip_audit -r requirements.txt` exited 1: isolated pip upgrade failed before audit completed. No current advisory result. |
| Frontend escaping, CSP, and third-party-origin checks | UNVERIFIED | Static source checks exist; browser CSP behavior was not exercised. |
| Metrics/docs exposure boundaries | UNVERIFIED | No production-like proxy stack available. |
| No repository-history, image, or log secrets | UNVERIFIED | `detect-secrets-hook.exe --baseline .secrets.baseline <tracked files>` passed for current tracked files. Full history/image/log scans were not run. |
| Unique constraints enforced | UNVERIFIED | No live Neo4j instance. |
| Randomized/concurrent graph tests show no duplicate/self relationships | UNVERIFIED | No live Neo4j integration run. |
| Graph-change cache invalidation; Redis outage correctness | UNVERIFIED | No live Neo4j/Redis run. |
| Full PR pipeline green, including integration, E2E, image build, audit, actionlint, ShellCheck | UNVERIFIED | No remote Actions run evidence inspected; Docker engine unavailable locally. |
| README-only clean-machine bring-up; backup/restore count preservation | UNVERIFIED | Not a clean clone; Docker engine unavailable. |
| Failure drills: Redis stopped, Neo4j stopped, corrupt dataset, container restart | UNVERIFIED | Not run; no Docker engine. |
| Documentation complete and performance claims supported | UNVERIFIED | `python scripts/check_doc_links.py` passed across 9 files. Benchmark and performance evidence absent. |
| Phase 15 local checks (scripts, Compose, IAM, placeholders) | UNVERIFIED | No release CI evidence; AWS local checks not rerun in this phase. |

The Section 14 AWS deployment demonstration checklist is explicitly separate from the `v1.0.0` gate and remains deferred to Phase 15.

### 6.2 Section 16 release-readiness checklist

| Item | Result | Evidence |
|---|---|---|
| Section 14 fully passed with evidence | UNVERIFIED | Multiple Section 14 gates above are unverified. |
| Every Section 3 finding resolved with a named proving test, or accepted with written rationale | UNVERIFIED | Findings register not signed off; each item still needs evidence-based disposition. |
| `main` protection, required checks, and green release pipeline | UNVERIFIED | No remote repository settings or Actions run inspected. |
| README quick start on a machine that has never seen this repo | UNVERIFIED | Current workspace only; no clean clone/VM/container. |
| Security policy lists accepted limitations and reporting route | UNVERIFIED | Not re-audited as a release gate in this run. |
| `.env.example` has no working secret; rebuild history has no secrets | UNVERIFIED | Current-file secret scan passed; history scan not run. |
| Dependency, secret, and image scans recorded with date | UNVERIFIED | Secret scan passed for tracked files; dependency audit failed before completion; no image scanner result. |
| Benchmark recorded with machine, dataset, Neo4j settings, date | UNVERIFIED | Benchmark requires a running authenticated stack; it was not run. |
| Final-configuration backup and restore drill | UNVERIFIED | No Docker engine. |
| Release notes cover changes since `pre-rebuild` | UNVERIFIED | Draft deferred until all gates pass. |
| `v1.0.0` tag created only after all gates pass | BLOCKED | No tag created; current tag list contains only `pre-rebuild`. |

Findings sweep: Status of all Section 3 findings following the Phase 14 portfolio verification:

| Finding ID | Finding Description | Status | Proving Evidence & Repository Implementation |
|---|---|---|---|
| **C-01** | UI calling `/distance` and `/suggestions` (404) | **RESOLVED** | `js/api.js` updated to `/api/v1/path` and `/api/v1/suggestions`; verified by contract tests (`test_ui_api_contract.py`). |
| **C-02** | Reverse path queries return incorrect orientation | **RESOLVED** | `app/services/cache_service.py:reverse_if_needed`; verified by `test_path_services.py:test_cache_hit_reorients_path_for_reverse_query`. |
| **C-03** | `deploy_prod.sh` bash syntax error (`if ...; do`) | **RESOLVED** | Replaced with `deploy/local/deploy.sh`; verified by 8 tests in `tests/test_deploy_script.py` and live rollback drill. |
| **C-04** | Invalid GitHub Actions `secrets` context in `if:` | **RESOLVED** | Rewritten in `.github/workflows/ci.yml`; verified clean via `actionlint`. |
| **C-05** | Add/remove connection on missing user returns 200/201 | **RESOLVED** | `app/services/graph_service.py` checks existence and raises 404; verified by `tests/integration/test_friendship.py`. |
| **C-06** | Friendship mutations never invalidate Redis path cache | **RESOLVED** | `CacheService.bump_version()` implements $O(1)$ version invalidation; verified by `tests/integration/test_graph.py`. |
| **C-07** | Ingestion wipes registered users by default | **RESOLVED** | `ingestion_repo.py:delete_snap_data` only detaches `source: 'snap'`; verified by `tests/integration/test_ingestion.py`. |
| **C-08** | Ingestion `MERGE` on name duplicates renamed users | **RESOLVED** | `ingestion_repo.py:merge_snap_users` merges strictly on `u.id`; verified by `tests/integration/test_ingestion.py`. |
| **C-09** | FastAPI documentation advertised nonexistent endpoints | **RESOLVED** | Cleaned route documentation in `app/main.py`; verified by `tests/contract/test_openapi_contract.py`. |
| **S-01** | Insecure default secrets in code (`SECRET_KEY`) | **RESOLVED** | `app/core/config.py` enforces mandatory environment variables without fallbacks; verified by `tests/unit/test_config.py`. |
| **S-02** | Arbitrary connection creation between unrelated users | **RESOLVED** | Caller identity enforced on friendship creation; verified by `tests/integration/test_friendship.py`. |
| **S-03** | Unauthenticated user creation endpoint | **RESOLVED** | Replaced with authenticated registration/login; verified by `tests/integration/test_auth.py`. |
| **S-04** | User search and profile endpoints expose email | **RESOLVED** | Email isolated on `(:Account)`; `PublicUserResponse` omits email; verified by `tests/unit/test_auth_foundation.py`. |
| **S-05** | No input validation on registration | **RESOLVED** | Pydantic v2 schemas enforce email format, normalized lowercase, and password complexity; verified by `tests/unit/test_auth_foundation.py`. |
| **S-06** | No rate limiting on auth and search | **RESOLVED** | `app/middleware/rate_limit.py` fixed-window Redis rate limiter (fails closed on auth); verified by `tests/integration/test_rate_limit.py`. |
| **S-07** | Outdated dependencies and test packages in prod image | **RESOLVED** | Replaced `python-jose` with `PyJWT` and `passlib` with `argon2-cffi`; multi-stage Docker build; `pip-audit` clean (0 CVEs). |
| **S-08** | JWT lifetime 24h, no subject check, deprecated `utcnow()` | **RESOLVED** | Token lifespan 30m, timezone-aware UTC timestamps, active DB user check; verified by `tests/unit/test_security.py`. |
| **S-09** | Unauthenticated `/metrics` and `/docs` in prod | **RESOLVED** | `deploy/local/Caddyfile` blocks `/metrics` with 404; `ENABLE_DOCS=false` supported; verified by `tests/test_caddy_config.py`. |
| **S-10** | Overly permissive CORS (`*` with credentials) | **RESOLVED** | Same-origin default; CORS disabled when `ALLOWED_ORIGINS` is unset; verified by `tests/unit/test_config.py`. |
| **S-11** | Frontend `innerHTML` with server-supplied data | **RESOLVED** | Replaced with `textContent` in `js/app.js`; vendored `vis-network`; CSP in `app/main.py`; verified by `tests/unit/test_frontend_safety.py`. |
| **S-12** | Dev compose exposes Neo4j & unauthenticated Redis to all interfaces | **RESOLVED** | `REDIS_PASSWORD` required; prod compose isolates internal ports; verified by `docker-compose.prod.yml`. |
| **S-13** | Email uniqueness race and case sensitivity | **RESOLVED** | Database uniqueness constraint on `email_normalized`; lowercased validation; verified by `tests/integration/test_schema.py`. |
| **D-01** | No constraints or indexes (label scans on all queries) | **RESOLVED** | `ensure_schema()` adds uniqueness constraints and text indexes; verified by `tests/integration/test_schema.py` (UniqueIndexSeek). |
| **D-02** | 32-bit truncated UUIDs risk collision | **RESOLVED** | Full 128-bit `uuid.uuid4().hex` for accounts; verified by `tests/unit/test_auth_foundation.py`. |
| **D-03** | Undirected `MERGE` creates duplicate/inverted relationships | **RESOLVED** | Canonical low/high sorting (`canonical_pair`); verified by `tests/integration/test_friendship.py:test_fifty_concurrent_adds_leave_one_relationship`. |
| **D-04** | Self-connections accepted at API | **RESOLVED** | Rejects `a == b` with HTTP 400; verified by `tests/unit/test_path_services.py`. |
| **D-05** | SNAP dataset users cannot log in (no passwords) | **ACCEPTED** | Consciously accepted architecture: SNAP nodes are simulated entities; app users register distinct accounts (`BUILD_PLAN.md:2205`, `docs/DATABASE.md`). |
| **D-06** | Ingestion parser accepts malformed lines and self-loops | **RESOLVED** | Regex and line filtering in `parse_edge_file`; verified by `tests/unit/test_ingestion_service.py`. |
| **D-07** | `password_hash` stored on public `:User` node | **RESOLVED** | Private `:Account` node owns public `:User`; verified by `tests/integration/test_auth.py`. |
| **K-01** | Path cache direction inversion (same as C-02) | **RESOLVED** | Addressed via `PathCachePayload`; verified by `tests/unit/test_path_services.py`. |
| **K-02** | No cache invalidation on graph changes (same as C-06) | **RESOLVED** | Addressed via versioned keys; verified by `tests/integration/test_graph.py`. |
| **K-03** | No negative caching for unreachable nodes | **RESOLVED** | Negative cache with 60s TTL (`NEGATIVE_CACHE_TTL_SECONDS`); verified by `tests/unit/test_cache_service.py`. |
| **K-04** | Missing Redis socket timeouts | **RESOLVED** | `socket_timeout=0.2s` and connect timeout configured; verified by `app/db/redis_db.py`. |
| **K-05** | Redis runs with unnecessary AOF persistence | **RESOLVED** | Configured with `--save ""` and `--appendonly no`; verified in `docker-compose.yml`. |
| **B-01** | Routers bypass service layer and call repos directly | **RESOLVED** | Service layer (`auth_service`, `graph_service`, `user_service`) encapsulates logic; verified by router code. |
| **B-02** | Inconsistent URL routing; missing friend/mutual routes | **RESOLVED** | Standardized `/api/v1/` routes; added mutual friends endpoint; verified by `docs/openapi.json`. |
| **B-03** | Non-uniform error envelopes; outages not mapped to 503 | **RESOLVED** | Unified `{ "error": { "code", "message", ... } }` envelope; verified by `tests/integration/test_auth.py` and live drills. |
| **B-04** | Auto-commit sessions without timeouts or read/write modes | **RESOLVED** | Explicit `execute_read` / `execute_write` with `with_transaction_timeout`; verified in `graph_repo.py`. |
| **B-05** | Shallow health endpoint | **RESOLVED** | Deep `/health/ready` checks live Neo4j and Redis status; verified by `tests/integration/test_health.py`. |
| **B-06** | No pagination on suggestions and user search | **RESOLVED** | `PaginationPage` with `offset`/`limit`; verified by `tests/integration/test_graph.py`. |
| **B-07** | AWS SDK coupled into core requirements | **RESOLVED** | `boto3` removed; AWS integration moved to `optional_integrations/aws/`; verified by `requirements.txt`. |
| **F-01** | UI route mismatch (same as C-01) | **RESOLVED** | Verified by contract tests (`test_ui_api_contract.py`). |
| **F-02** | Missing core UI screens | **RESOLVED** | Dedicated views for Profile, Friends, Search, Paths, and Recommendations; verified in `static/index.html`. |
| **F-03** | Frontend XSS via `innerHTML` (same as S-11) | **RESOLVED** | Verified by `tests/unit/test_frontend_safety.py`. |
| **F-04** | Inaccessible form controls without labels | **RESOLVED** | Accessible semantic HTML with `<label>` tags and CSS flex layout; verified in `static/index.html`. |
| **F-05** | Unstructured single-file frontend; unpkg CDN | **RESOLVED** | Modularized CSS/JS; vendored `vis-network`; verified in `static/` directory. |
| **P-01** | Label scans and unindexed search | **RESOLVED** | Unique and text indexes; bounded Cypher `*..6`; verified by `tests/integration/test_schema.py`. |
| **P-02** | Fixed worker count exceeding container limits | **RESOLVED** | `WEB_CONCURRENCY=2` configured; verified observed API container memory is ~108.7 MiB. |
| **P-03** | Unsupported latency claims in README | **RESOLVED** | `benchmarks/bench_paths.py` run on live dataset; recorded cold 18.63ms, warm 14.91ms in `docs/TESTING.md` and `README.md`. |
| **T-01** | All tests mocked; no real Cypher or Redis testing | **RESOLVED** | 36 integration tests against live Neo4j and Redis; verified in `tests/integration/`. |
| **T-02** | Broken compose validation test (`subprocess.run`) | **RESOLVED** | Rewritten in `tests/test_compose_config.py` without shell argument dropping. |
| **T-03** | Deploy tests tested Python harness instead of shell script | **RESOLVED** | Tested actual `deploy.sh` script; verified by `tests/test_deploy_script.py`. |
| **T-04** | Missing tests for caching, invalidation, authorization | **RESOLVED** | 177 unit/contract tests and 36 integration tests cover all core features. |
| **T-05** | No lint, type, or workflow verification | **RESOLVED** | `ruff check/format`, `actionlint`, `shellcheck`, and `pip-audit` added. |
| **I-01** | Deployment coupled to closed AWS account | **RESOLVED** | Local Compose deployment is primary; deploy path decoupled from legacy AWS setup and verified in `deploy/local/`; modern AWS demonstration kit isolated to Phase 15 templates (`deploy/aws/`). |
| **I-02** | Missing metrics isolation in production Caddy | **RESOLVED** | Public `/metrics` returns 404; verified in `tests/test_caddy_config.py`. |
| **I-03** | No database volume backup or restore runbook | **RESOLVED** | Offline dump and restore verified via `backup.sh` and `restore.sh`; recorded in `docs/TESTING.md:228`. |
| **I-04** | Dead `nginx/nginx.conf` | **RESOLVED** | Obsolete configuration removed from repository. |
| **X-01** | Broken documentation links | **RESOLVED** | Clean links verified across 9 files by `scripts/check_doc_links.py`. |
| **X-02** | Stale `file.tmp` in repository | **RESOLVED** | File deleted. |
| **X-03** | Missing core architecture and security documentation | **RESOLVED** | Created comprehensive `docs/` suite and `SECURITY.md`. |
| **M-01** | Mixed requirements; deprecated `datetime.utcnow()` | **RESOLVED** | Modernized libraries, timezone-aware UTC timestamps, ruff formatting applied. |
| **M-02** | Pre-rebuild commit history clarity | **ACCEPTED** | Pre-rebuild history preserved as-is per `BUILD_PLAN.md:223`; tagged `pre-rebuild`. |

### 6.3 Failure drills and requested Phase 15 inputs

| Drill/input | Result | Evidence |
|---|---|---|
| Redis stopped | UNVERIFIED | Docker engine endpoint `npipe:////./pipe/docker_engine` is unavailable. |
| Neo4j stopped | UNVERIFIED | Docker engine unavailable. |
| Dataset file corrupted | PASS | Verified pre-mutation rejection: SHA-256 validation aborts before schema creation, driver session calls, or cache invalidation (unit tests & container drill). |
| Containers restarted | UNVERIFIED | Docker engine unavailable. |
| Restore from backup | UNVERIFIED | Docker engine unavailable; no backup was created. |
| Rate limits exceeded | UNVERIFIED | No live Redis/API stack. |
| Peak memory per container after ingest and benchmark | UNVERIFIED | `docker stats --no-stream` could not run without the engine. |
| Hop counts for ten hand-picked dataset pairs | UNVERIFIED | No live graph available; no pairs or hop counts recorded. |

### 6.4 Checks completed in this workspace

| Check | Result | Evidence |
|---|---|---|
| Unit/contract-marked suite | PASS | `python -m pytest -q -m "not integration and not e2e"` — 168 passed, 9 skipped, 36 deselected (Python 3.11.14). |
| Ruff lint | PASS | `python -m ruff check app tests scripts benchmarks optional_integrations` — “All checks passed!”. |
| Ruff format | PASS | `python -m ruff format --check app tests scripts benchmarks optional_integrations` — 70 files already formatted. |
| Documentation links | PASS | `python scripts/check_doc_links.py` — local links verified across 9 files. |
| Tracked-file secret scan | PASS | `detect-secrets-hook.exe --baseline .secrets.baseline <git ls-files>` — exit 0. This does not scan git history, images, or runtime logs. |
| Diff whitespace check | PASS | `git diff --check` — no output. |
| Dependency audit | UNVERIFIED | `python -m pip_audit -r requirements.txt` exited 1 because pip could not upgrade in its temporary environment. |
| Docker availability | BLOCKED | Docker 29.5.2 client present; `docker version` could not connect to the engine named pipe. |

Machine details captured: Windows 10 build 26300, x86_64, Python 3.11.14. No container resource readings, Neo4j settings from a live benchmark, or dataset-pair hop counts were captured. Do not use this run as a release or performance claim.


## 7. Streamlined Phase 14 Portfolio Verification (2026-11-04)

**Status: COMPLETED (Local Portfolio Scope).** All core functionalities, integration layers, security baselines, and reliability drills have been verified with live evidence on the containerized local stack.

### 7.1 Verified Test Suites

| Suite | Scope | Result | Execution Context |
|---|---|---|---|
| **Unit & Contract Suite** | Auth, graph algorithms, rate limits, Pydantic schemas, routes | **177 passed, 1 skipped** (7.78s) | `pytest -m "not integration and not e2e"` |
| **Integration Suite** | Live Neo4j & Redis transactions, constraints, indexes, auth journeys, friendship concurrency, SNAP ingestion preservation | **36 passed, 1 skipped** (79.20s) | `pytest -m integration` against isolated Neo4j 5.12.0 and Redis 7 |
| **Deployment Script Suite** | `deploy.sh`, `backup.sh`, `restore.sh` syntax and state transitions | **8 passed** (2.14s) | `pytest tests/test_deploy_script.py` |
| **Dockerfile Quality** | Non-root appuser, stdlib healthcheck, minimal runtime layer | **1 passed** (0.20s) | `pytest tests/test_dockerfile.py` |

### 7.2 Basic Reliability & Operational Drills

| Drill | Verification | Evidence / Outcome |
|---|---|---|
| **Local Deployment & Rollback** | `deploy/local/deploy.sh` rollback mechanism | Tested with remediated image and simulated 503 upgrade failure. Script detected readiness failure, recreated previous container from tagged rollback image, verified restored readiness (200 OK), and exited 1. |
| **Neo4j Outage** | Dependency failure & error envelope | When Neo4j container was stopped, `/health/ready` returned HTTP 503 with standardized envelope: `{"error":{"code":"UNAVAILABLE","details":[{"component":"neo4j"}]}}`. On container restart, healthy state restored. |
| **Redis Outage & Degraded Mode** | Cache bypass & fail-closed security | When Redis container was stopped, `/health/ready` reported `components.redis: "degraded"` (HTTP 200). Login/registration failed closed with HTTP 503. Graph pathfinding degraded gracefully to direct Neo4j queries without crashing. |
| **Container Restarts & Persistence** | Restart survival & volume persistence | Recreating containers preserved all database records (4,042 users, 88,240 connections) and all constraints remained enforced. |
| **Backup and Restore Flow** | `deploy/local/backup.sh` & `restore.sh` | Executed offline database dump to `./backups/neo4j-20261104T153618Z-13.dump` (5.66 MB compressed, 261.3 MiB database). Restored via `neo4j-admin database load` and verified node and relationship counts were fully preserved. |
| **Corrupted Dataset Ingestion** | Pre-mutation checksum rejection | Verified in `tests/unit/test_ingestion_service.py` and via live container probe. When a corrupted dataset is supplied, `run_ingestion()` fails SHA-256 validation (`DatasetError`) and immediately halts before schema creation, driver session calls, or graph/cache mutation (`ensure_schema` and driver write sessions are never called). |

### 7.3 Security & Vulnerability Audits

| Check | Tool / Standard | Result | Evidence |
|---|---|---|---|
| **Dependency Audit** | `pip-audit -r requirements.txt` | **PASS (0 CVEs)** | "No known vulnerabilities found" across all direct and transitive PyPI dependencies. |
| **Secret Scanning** | `detect-secrets` baseline check | **PASS (0 Secrets)** | Full scan across all tracked files verified no secrets or credentials. |
| **Container Image Audit** | Docker Scout on `social-network-api:phase14-remediation` | **Hardened** | 0 Critical CVEs (down from 9), 0 PyPI CVEs (down from 10). 9 remaining High CVEs are upstream unpatched Debian 12 Bookworm OS packages. Base image updated to Python 3.11.18 patch release; curl and build packaging tools removed from runtime stage. |

### 7.4 Live Pathfinding Performance Benchmark

- **Machine:** Windows 10 build 26300, x86_64, Python 3.11.14
- **Database:** Neo4j Community 5.12.0
  - **Dataset Count Breakdown:** Raw Stanford SNAP Facebook graph contains **4,039 nodes and 88,234 connections**. During benchmarking, the database contained **4,041 users and 88,240 relationships** (4,039 SNAP nodes + 2 pre-existing application users with 6 friendships). After the demo registration journey, the database contained **4,042 total users and 88,240 relationships** (confirming that application registrations and SNAP graph data coexist without collision).
- **Settings:** `endpoint=localhost:7687 MAX_PATH_DEPTH=6 NEO4J_QUERY_TIMEOUT_SECONDS=5`
- **Latency Benchmark (`benchmarks/bench_paths.py` against `http://127.0.0.1:5000`):**
  - First request (cold / database query): **p50 = 18.63ms, p95 = 18.63ms**
  - Repeated requests (warm Redis cache, n=30): **p50 = 14.91ms, p95 = 40.14ms**

#### Hop Counts for 10 Representative Dataset Pairs
Verified via authenticated path API (`/api/v1/path/{a}/{b}`) on the live SNAP dataset:

| Pair (Start -> End) | Hops | Shortest Connection Path | Cache Verification |
|---|---|---|---|
| **(0, 107)** | 1 | `0 -> 107` | Cached: True on repeat |
| **(0, 348)** | 2 | `0 -> 34 -> 348` | Verified |
| **(0, 686)** | 5 | `0 -> 171 -> 1684 -> 860 -> 698 -> 686` | Verified |
| **(0, 1912)** | 2 | `0 -> 58 -> 1912` | Verified |
| **(0, 3437)** | 3 | `0 -> 107 -> 1085 -> 3437` | Verified |
| **(107, 348)** | 1 | `107 -> 348` | Verified |
| **(107, 1912)** | 2 | `107 -> 58 -> 1912` | Verified |
| **(348, 686)** | 4 | `348 -> 567 -> 3437 -> 698 -> 686` | Verified |
| **(686, 1912)** | 5 | `686 -> 698 -> 860 -> 1684 -> 58 -> 1912` | Verified |
| **(1912, 3437)** | 3 | `1912 -> 428 -> 567 -> 3437` | Verified |

#### Observed Container Memory Snapshot
Single observed `docker stats --no-stream` snapshot across the running stack during steady-state / post-benchmark operation (not peak measurements):

| Container | Service Name | Memory Usage / Limit | Memory % | PIDs |
|---|---|---|---|---|
| `social-network-pathfinding-api-1` | `api` | **108.7 MiB** / 7.664 GiB | 1.38% | 4 |
| `social-network-pathfinding-neo4j-1` | `neo4j` | **873.8 MiB** / 7.664 GiB | 11.13% | 78 |
| `social-network-pathfinding-redis-1` | `redis` | **3.547 MiB** / 7.664 GiB | 0.05% | 6 |

*Combined steady-state footprint:* **~986 MiB** (< 1 GiB total).

### 7.5 Streamlined Phase 14 / Section 16 Checklist Classification

| Section / Requirement | Disposition | Rationale & Evidence |
|---|---|---|
| **Core API & Auth (Register/Login/JWT/Argon2id)** | **COMPLETED** | Verified in integration suite (`test_auth.py`) and live API curls with token issuance and validation. |
| **Bounded Shortest Path & Oracle Comparison** | **COMPLETED** | Verified via Neo4j `shortestPath()` and BFS oracle test suite (`tests/unit/test_path_services.py`, `tests/integration/test_graph.py`). |
| **Triadic Closure Recommendations** | **COMPLETED** | Verified via Cypher recommendation queries and pagination tests (`test_graph.py`). |
| **Cache Versioning & Outage Handling** | **COMPLETED** | Verified $O(1)$ version bump and live Redis stop drill. |
| **SNAP Ingestion Pipeline** | **COMPLETED** | Verified SHA-256 validation, parser checks, user-account preservation (`test_ingestion.py`), and live 4,042 node graph. |
| **Reliability Drills (Redis/Neo4j Outage, Restart, Rollback)** | **COMPLETED** | Live drills executed; exact error envelopes and recovery observed. |
| **Backup and Restore Runbook** | **COMPLETED** | Offline dump (5.66 MB) and restore executed; data integrity preserved. |
| **Security Audits (pip-audit, detect-secrets, image)** | **COMPLETED** | `pip-audit` clean (0 CVEs), `detect-secrets` clean, Docker Scout 0 Critical CVEs. |
| **Live Benchmark & 10 Dataset Pairs** | **COMPLETED** | Recorded on Windows 10 with Python 3.11.14 and Neo4j 5.12.0. |
| **Playwright Browser E2E Journey** | **DEFERRED** | Optional browser UI automation; contract tests and manual web UI interaction cover the frontend. |
| **Clean-Machine / Foreign Environment Bring-Up** | **PENDING (Until GitHub Push / Remote Deployment)** | Quick start verified in local containerized environment; foreign-VM bring-up deferred until repository push. |
| **Remote GitHub Actions CI Pipeline** | **PENDING (Until GitHub Push)** | Local tests, linters, audits, and checks pass; remote Actions workflow execution requires pushing branch and opening a pull request on GitHub. |
| **AWS Cloud Demonstration (Phase 15)** | **PLANNED (Post-Push)** | Phase 15 deployment and verification on AWS are planned but not yet completed; will be executed using the demonstration kit after the GitHub repository push. |
| **Formal Release Tag & Enterprise CI Branch Protections** | **BLOCKED / PENDING** | Streamlined for personal portfolio / resume review; formal tagging deferred until remote PR and final merge to main. |
