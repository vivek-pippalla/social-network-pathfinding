# Social Network Pathfinding — Implementation Status

> Record verified work only. Do not mark work complete based on intention or unverified agent claims.

## Project controls
- **Master plan:** `BUILD_PLAN.md` — Social Network Pathfinding: Reconstruction Blueprint
- **Working branch:** phase-8-api-completion (stacked on Phase 7 commit 563e037; main unchanged)
- **Protected baseline:** `main` — do not modify directly
- **Current phase:** Phase 8 — API completion and contract
- **Overall status:** In progress
- **Last verified update:** 2026-11-03

## Phase checklist

| Phase | Status | Evidence / notes |
|---|---|---|
| Phase 0: baseline, cleanup, dependency refresh | Complete locally; final review pending | Pushed branch remains unmerged by plan; final integrated review and merge are deferred until all phases are complete |
| Phase 1: Application foundation | Complete locally; awaiting user review | Stacked from Phase 0; local acceptance checks recorded below; no commit created |
| Phase 2: Graph schema and real-infrastructure test harness | Implemented and committed; integration verification deferred | Commit 6bb16bb on phase-2-graph-schema-test-harness; user directed deferral until environment setup is complete |
| Phase 3: Authentication and authorisation | Implemented and committed; real-service verification deferred | Commit f1caf0a on phase-3-authentication-authorization; real Neo4j/Redis checks remain unverified |
| Phase 4: Users and friendship | Implemented and committed; real-service verification deferred | Commit 5058eff on phase-4-users-friendship; concurrency, query-plan, and self-loop behavior remain unverified |
| Phase 5: Pathfinding and recommendations | Implemented and committed; real-service verification deferred | Commit 46458ed on phase-5-pathfinding-recommendations; live path and recommendation behavior remains unverified |
| Phase 6: Redis caching and invalidation | Implemented and committed; real-service verification deferred | Commit 610222b on phase-6-redis-caching-invalidation; cache consistency guarantee and local checks recorded below |
| Phase 7: Dataset ingestion | Implemented and committed; real-service verification deferred | Commit 563e037 on phase-7-dataset-ingestion; checksum and parser checks passed, real graph ingestion remains unverified |
| Phase 8: API completion and contract | In progress | OpenAPI contract, response metadata, pagination, body-size enforcement, and token-protected metrics are being verified locally; no commit created |

Status values: `Not started`, `In progress`, `Blocked`, `Complete`, `Deferred / optional`.

## Current task log

### Phase 0
- **Status:** Local implementation and gates complete; branch pushed and intentionally unmerged until final project integration.
- **Branch and baseline:** phase-0-baseline-cleanup at 51bf07b; pre-rebuild points to e5fd4ea; main remains unchanged.
- **Checks:** baseline `pytest -q` 54 passed; current standard non-integration and full suites 55 passed each; Ruff and actionlint clean; pip-audit findings documented.
- **Known unverified items:** Optional boto3/watchtower pins were not installed per user instruction; a fresh runtime-only environment was not created; Docker daemon and ShellCheck are unavailable; archived deploy_prod.sh retains the known C-03 syntax error for Phase 11 replacement.

## Phase completion record

For each phase, append:
- Date and phase/task
- Summary and files changed
- Acceptance criteria addressed
- Commands/checks actually run and results
- Checks not run and reasons
- Deviations, limitations, known risks
- Reviewer decision / user approval to continue

## Rules
- A phase is complete only when its acceptance criteria have been checked and evidence recorded.
- Keep failed or unavailable checks visible.
- Do not move to the next phase without explicit user approval.
- Preserve user changes; no destructive data or repository operations without approval.


## Phase 0 progress (2026-11-02)

- **Status:** In progress on branch `phase-0-baseline-cleanup`; baseline tag `pre-rebuild` points to `e5fd4ea` on `main`.
- **Baseline:** Python 3.11.14 from the existing Conda `graph` environment; `pytest -q` before Phase 0 changes reported 54 passed.
- **Completed and committed:** stale file cleanup; initial Ruff/pytest configuration; runtime/dev/AWS requirements split; refreshes for framework/telemetry, Neo4j, Redis, Pydantic, authentication, and parser packages.
- **Implemented:** optional AWS imports, AWS legacy relocation, minimal CI, README and ignore cleanup, and compose config test correction.
- **Verified:** `ruff check .`; `ruff format --check .` (26 files); the standard non-integration command and full `pytest -q` (55 passed each); `actionlint` 1.7.12; `pip check`; Compose config validation and malformed-file rejection.
- **Audit:** `pip-audit -r requirements.txt` reported three rows across python-jose and ecdsa; triage is recorded in `docs/DEPENDENCY_AUDIT.md`. The audit is not clean.
- **Not verified:** refreshed boto3/watchtower pins were not installed, per user instruction; a fresh runtime-only environment was not created. Docker daemon is unavailable. `shellcheck` is not installed. The inactive legacy `deploy_prod.sh` retains its known syntax error (C-03), to be replaced in Phase 11.

- **Closeout:** Phase 1 began on the stacked branch after the Phase 0 implementation was pushed but before final integration review. User-provided `docs/BUILD_PLAN.md` and `docs/AGENTS.md` remain untracked and were not added to Phase 0 commits.

### Phase 1
- **Status:** In progress on phase-1-application-foundation, based on the pushed Phase 0 branch.
- **Plan workflow:** Updated locally for stacked branches, one approved commit per completed phase, and one final integration merge.
- **Checks:** `ruff check .` passed; `ruff format --check .` reported 28 files already formatted; standard non-integration suite 74 passed; full `pytest -q` 74 passed. `pip-audit -r requirements.txt --no-deps` reported three advisory rows across `python-jose` and `ecdsa`; dependency replacement remains scheduled for Phase 3. No Phase 1 integration or browser tests were defined or run.
- **Implemented:** Fail-fast settings and cached accessor; app factory; uniform sanitized error envelope; request-ID middleware and JSON access logging; liveness/readiness routes; conditional CORS and docs; corrected API description; CloudWatch handler moved to `optional_integrations/`; `.env.example` uses invalid placeholders; compatibility tests updated.
- **Known unverified:** No live Neo4j/Redis readiness check was run; health dependency behavior was tested with fakes. No real server/container startup was performed. The current `.env` lacks `SECRET_KEY`, so app startup correctly refuses until a private value is configured.

### Phase 2
- **Status:** Implementation complete on phase-2-graph-schema-test-harness, stacked from Phase 1 commit 97e6aff; real-service verification deferred by user until environment setup is complete.
- **Implemented:** Schema bootstrap, AUTO_SCHEMA lifespan hook, isolated test Compose stack and helper, real-service pytest fixtures/tests, and CI integration job.
- **Checks previously run:** Ruff check/format passed; 75 non-integration tests passed; full suite 75 passed and 5 integration tests skipped. Integration tests were not verified against live services. Docker/Bash access errors are documented; do not retry in this phase.
- **Known:** Real Neo4j and Redis behavior remains unverified until environment setup is complete.

### Phase 3
- **Status:** Implemented and committed on phase-3-authentication-authorization, stacked on Phase 2 commit 6bb16bb.
- **Implemented:** PyJWT/Argon2id account flow; separate Account/User creation transaction; normalized unique email handling; registration validation; dummy-hash login; Redis rate limiting; current-user existence check; private/public profile separation; removed open user creation and arbitrary connection routes; authentication tests and SECURITY.md draft.
- **Checks:** Ruff check passed; Ruff format check passed (40 files); non-integration suite passed (93 passed, 13 integration cases deselected, no warnings); full pip-audit runtime dependency graph reported no known vulnerabilities.
- **Unverified:** Real Neo4j/Redis integration suite, including concurrent registration and the deliberate dropped-constraint mutation check, was not run per user direction to defer real-service verification. Docker/Bash were not invoked.

### Phase 4
- **Status:** Implemented and committed on phase-4-users-friendship, based on Phase 3 commit f1caf0a.
- **Implemented:** Canonical friendship repository operations with managed transactions and query timeouts; service-level self/unknown-user rules and post-commit change hook; versioned friend list/add/remove/mutual routes; user profile/search delegation through services; indexed name search and ID validation; unit and real-service integration tests.
- **Local checks:** Ruff lint and format passed; `pytest -q -m "not integration and not e2e"` passed (101 passed, 20 deselected); integration collection found 20 tests. `git diff --check` passed.
- **Unverified:** No real Neo4j/Redis integration tests were executed per the prior deferral. The 50-way friendship concurrency result, text-index query plan, and Neo4j self-loop `MERGE` behavior require the dedicated integration services.
- **Dependency audit:** `pip-audit -r requirements.txt --cache-dir <temporary cache>` reported no known vulnerabilities.

### Phase 5
- **Status:** Implemented and committed on phase-5-pathfinding-recommendations, based on Phase 4 commit 5058eff; commit 46458ed.
- **Implemented:** Bounded Neo4j path queries and path/recommendation services; named path nodes; authenticated paged suggestion routes; deterministic distinct-mutual recommendations; Neo4j transaction-timeout error mapping; BFS oracle, randomized real-service tests, and a no-seeding HTTP benchmark script.
- **Local checks:** Ruff lint and format passed; `pytest -q -m "not integration and not e2e"` passed (117 passed, 25 deselected); integration collection found 25 tests; benchmark target-redaction tests passed; `benchmarks/bench_paths.py --help` passed; `pip-audit -r requirements.txt` reported no known vulnerabilities; `git diff --check` passed.
- **Unverified:** Real Neo4j/Redis tests were not run under the existing deferral, including 200-graph oracle comparison, bounded shortest-path behavior, recommendation distinctness/paging, and the 1,000-degree hub query. The timeout response was tested with the installed driver’s hydrated `ClientError`; no timeout was induced against a live Neo4j server. The benchmark was not run against a live stack, so no latency results are claimed.

### Phase 6
- **Status:** Implemented locally on `phase-6-redis-caching-invalidation`, stacked on Phase 5 commit 46458ed; not committed.
- **Implemented:** Versioned canonical path cache, reverse-direction reads, positive and negative TTLs, Redis timeout configuration and fail-open operations, graph-version invalidation after friend mutations, and disabled Redis persistence in the prod-like Compose command.
- **Consistency guarantee:** Successful graph-version increments make prior path entries unreachable immediately. Redis uses `volatile-lru`, so TTL path entries can be evicted while the non-expiring graph-version counter is protected from LRU eviction. If an increment fails, stale positive entries can remain for at most `CACHE_TTL_SECONDS` (300 seconds by default); negative entries expire after `NEGATIVE_CACHE_TTL_SECONDS` (60 seconds by default). If Redis reads fail, path requests bypass the cache and query Neo4j. Cache warnings are throttled per operation to one per 30 seconds.
- **Local checks:** `ruff check .` passed; `ruff format --check .` passed (53 files); `pytest -q -m "not integration and not e2e"` passed (131 passed, 31 deselected); `git diff --check` passed. The orientation regression test failed as expected with canonicalization/reversal temporarily removed, then passed in the restored implementation.
- **Unverified:** `REQUIRE_INTEGRATION=1 pytest -q -m integration` was attempted once and failed during service setup because Neo4j refused connections at `127.0.0.1:17687` (31 setup errors; 127 tests deselected). Real Neo4j/Redis cache, invalidation, outage, and shared-process behavior remains unverified; no retry or service-start workaround was attempted. The Redis outage test uses an unreachable Redis endpoint; the separate-process invalidation test is authored but could not be exercised.

### Phase 7
- **Status:** Implemented and committed on `phase-7-dataset-ingestion`, stacked on Phase 6 commit `610222b`; commit `563e037`.
- **Implemented:** Checksum-verified SNAP download/cache; strict edge-list parser with malformed, self-loop, duplicate and ignored counters; additive batched Neo4j ingestion with summary-counter results and post-check; SNAP-only reset plus separately confirmed full wipe; cache-version bump after graph changes; schema/reset-cache/demo-user CLI commands; unit and real-service integration tests.
- **Dataset terms:** The official [SNAP ego-Facebook page](https://snap.stanford.edu/data/ego-Facebook.html) describes the dataset and requests citation but does not state a dataset-specific redistribution license. SNAP's separate BSD page applies to SNAP software. The CLI therefore downloads the dataset directly and verifies its SHA-256 instead of asserting redistribution rights. The existing tracked archive under `scripts/` is preserved pending the user's decision about that pre-existing file.
- **Local checks:** `ruff check .` passed; `ruff format --check app tests` passed (50 files); non-integration tests passed (133 passed, 36 deselected); `pip-audit -r requirements.txt` reported no known vulnerabilities; `git diff --check` passed. Parsing the preserved archive took 0.299 seconds and produced 4,039 users and 88,234 valid edges with zero malformed, self-loop, or duplicate lines. Full-repository `ruff format --check .` was blocked by access-denied files in the task-created `.phase7-pip-audit-cache`; formatting all application and test code passed. The archive SHA-256 is `125e84db872eeba443d270c70315c256b0af43a502fcfe51f50621166ad035d7`.
- **Unverified:** Real Neo4j/Redis integration tests, including 4,039/88,234 loaded graph counts, idempotency, reset preservation, post-write counters, and graph-version behavior, remain deferred under the existing environment agreement. The actual ingestion duration and target machine therefore cannot be reported; no DB ingestion time is claimed. Docker/Bash were not used.

### Phase 8
- **Status:** Implemented locally on `phase-8-api-completion`, stacked on Phase 7 commit `563e037`; not committed.
- **Implemented:** Audited the Section 7.1 route inventory; added stable operation IDs, tags, response models/examples and documented error envelopes; unified paged responses; protected `/metrics` with Bearer authentication while excluding it from public OpenAPI; added a configurable request-body limit; added deterministic OpenAPI/API reference generation and contract tests; documented the API and added only narrow `.gitignore` exceptions for those generated deliverables.
- **Local checks:** `ruff check .` passed; `ruff format --check . --extend-exclude .phase7-pip-audit-cache` passed (62 files); `scripts/export_openapi.py --check` passed; `pytest -q -m "not integration and not e2e"` passed (143 passed, 36 deselected); `pip-audit -r requirements.txt` reported no known vulnerabilities; `git diff --check` passed.
- **Unverified:** No real Neo4j/Redis integration or full-stack e2e checks were run under the existing environment deferral. `/metrics` authentication and response were checked through TestClient, not with a live Prometheus scrape. Docker/Bash were not used.

### Phase 9
- **Status:** Implementation in progress on `phase-9-frontend-reconstruction`, stacked on Phase 8 commit `cf8c32f`; uncommitted pending review.
- **Implemented:** Replaced the single inline page with accessible HTML, responsive CSS, ES modules and a single API client using the committed OpenAPI routes; added authentication, dashboard, name/ID path selection with named graph, friend search/add/remove, suggestions and mutual friends, and profile views. Server-provided values are created as text nodes. Tokens are kept in memory and `sessionStorage`, then removed on 401 or expiry. Added same-origin CSP/security headers and vendored vis-network 10.1.2 with its MIT license and SHA-256.
- **CSP note:** Script, connection and other resource sources remain same-origin. `style-src 'unsafe-inline'` is limited to styles because the vendored vis-network standalone bundle sets inline canvas positioning/size.
- **Local checks:** `ruff check .` passed (with access-denied warnings while scanning the ignored audit cache); `ruff format --check . --extend-exclude .phase7-pip-audit-cache` passed (65 files). The non-integration/non-e2e suite passed (148 passed, 1 skipped, 36 deselected); all 4 frontend contract/accessibility checks passed. Vendored asset and license hashes were computed and recorded. `git diff --check` passed.
- **Unverified:** Browser end-to-end journey, visual/mobile behavior, actual CSP behavior in a browser, and screen-reader/manual keyboard checks were not run. Playwright is not installed here; its e2e module was skipped for that reason. `pip-audit -r requirements.txt` did not complete: pip-audit failed while trying to upgrade pip in its temporary environment. Real Neo4j/Redis integration and full stack startup remain deferred. To run e2e from PowerShell: install dev requirements with `python -m pip install -r requirements-dev.txt`, then `python -m playwright install chromium`; create `.env` from `.env.example` and replace its secret placeholders locally; start the configured stack with `docker compose up -d --build`; then run `$env:BASE_URL='http://127.0.0.1:5000'; python -m pytest -q -m e2e tests/e2e/test_smoke.py`.
- **Manual accessibility checklist (not completed):** tab through sign-in/register, each navigation item and all forms; verify focus moves to each screen heading; confirm focus indicators and live announcements; operate suggestions, friend controls, mutual view and graph without a mouse; inspect a 375px-wide viewport; check graph labels and path text with a screen reader; verify reduced-motion behavior and color contrast.
