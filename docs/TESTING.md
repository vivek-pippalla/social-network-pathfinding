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
