# Social Network Pathfinding — Implementation Status

> Record verified work only. Do not mark work complete based on intention or unverified agent claims.

## Project controls
- **Master plan:** `BUILD_PLAN.md` — Social Network Pathfinding: Reconstruction Blueprint
- **Working branch:** phase-12-ci-cd (stacked on Phase 11 commit d8829df; main unchanged)
- **Protected baseline:** `main` — do not modify directly
- **Current phase:** Phase 12 — CI/CD
- **Overall status:** In progress
- **Last verified update:** 2026-11-04

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
| Phase 8: API completion and contract | Implemented and committed | Commit cf8c32f on phase-8-api-completion; API contract and local checks recorded below |
| Phase 9: Frontend reconstruction | Implemented and committed | Commit 9c9ab34 on phase-9-frontend-reconstruction; browser E2E and real-service verification remain deferred |
| Phase 10: Observability | Implemented and committed | Commit 6c6b82f on `phase-10-observability`; local tests passed, live monitoring and real-service checks remain unverified |
| Phase 11: Docker and local deployment | Implemented and committed; live verification deferred | Commit d8829df on `phase-11-docker-local-deployment`; live Docker checks remain unverified |
| Phase 12: CI/CD | In progress | Branch `phase-12-ci-cd`, stacked on Phase 11 commit d8829df |

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

### Phase 10
- **Status:** Implemented and committed on `phase-10-observability`, stacked on Phase 9 commit `9c9ab34`; commit `6c6b82f`.
- **Implemented:** Prometheus counters and histograms for cache, path, friendship, authentication, rate limiting, and Neo4j repository operations; structured safe domain events with HMAC email identifiers; source-IP-based `/metrics` access limited to loopback and private network peers (forwarded headers are ignored); development API and monitoring ports bind to localhost; Caddy denies `/metrics` before proxying public traffic; Prometheus/Grafana monitoring profile, provisioned datasource/dashboard, and environment-supplied Grafana credentials with empty and example-placeholder startup guards.
- **Local checks:** Ruff lint passed; Ruff format check passed (61 files); `scripts/export_openapi.py --check` passed; `pytest -q -m "not integration and not e2e" -k "not test_docker_compose_config_validation"` passed (158 passed, 1 skipped, 37 deselected); Compose/Caddy configuration unit checks ran in that suite; `git diff --check` passed; `pip-audit -r requirements.txt` passed with no known vulnerabilities during implementation. The Docker-dependent Compose test was excluded by request.
- **Unverified:** Real Neo4j/Redis integration remains deferred under the existing environment agreement. Docker Compose is installed, but `docker info` could not access the Docker engine named pipe (permission denied), so the monitoring profile and Caddy proxy were not started; no live dashboard panels or proxy behavior were observed. Caddy denial is covered by a static configuration assertion only.

### Phase 11
- **Status:** Implementation complete locally on `phase-11-docker-local-deployment`, stacked on Phase 10 commit `6c6b82f`; uncommitted pending review.
- **Implemented:** Rebuilt the runtime Dockerfile around `requirements.txt`, a pinned Python base, a non-root user, configurable `WEB_CONCURRENCY`, explicit Uvicorn proxy trust, and `/health`. Split base Compose from the loopback-only development override; added prod-like Caddy edge settings, Redis authentication without persistence, Neo4j memory settings, and explicit restart policies. Added local deployment with previous-image rollback, offline Neo4j dump/restore scripts, Compose profile checks, behavior tests using fake Docker/curl, a local deployment README, and this status record. The SNAP archive remains fetched and checksum-verified at ingestion time, and is excluded from the image context under the existing data redistribution decision.
- **Local checks:** `ruff check .` passed; Ruff format check passed (71 files); non-integration/non-e2e suite passed (156 passed, 9 skipped, 36 deselected); Compose model tests passed for development, monitoring, and prod-like edge configurations; `scripts/export_openapi.py --check` passed with temporary valid settings; `pip-audit -r requirements.txt` passed with no known vulnerabilities; `git diff --check` passed. The three shell syntax tests, four deployment scenarios, and syntax mutation test were authored against the real scripts but skipped because the available Windows `bash.exe` launcher could not execute; the Compose config tests ran successfully without needing the Docker daemon. The remaining skipped test is the browser test because Playwright is not installed.
- **Neo4j pin decision:** Existing `neo4j:5.12.0` is retained pending approval. Neo4j's release archive lists `5.26.32` (9 October 2026) as the latest 5.x candidate. A Neo4j version change is not made in this phase without explicit approval; back up and test restore before changing it.
- **Unverified:** `docker info` returned permission denied for `npipe:////./pipe/docker_engine`; no image build, service start, SNAP ingestion, health request, UI login, or backup/restore drill was run. `bash -n` and the behavioral deploy cases skipped because Windows `bash.exe` could not run; `shellcheck` is not installed. The command syntax is linked to the official current Neo4j manual, but the exact behavior against pinned image `5.12.0` was not verified. Playwright/browser and real Neo4j/Redis acceptance checks remain unverified.
- **Clean-machine commands:** In a fresh clone only, copy `.env.example` to `.env`; generate a 32-byte hex `SECRET_KEY` and independent 24-byte hex `NEO4J_PASSWORD` and `REDIS_PASSWORD` values with `openssl rand -hex 32` / `openssl rand -hex 24`, then replace the placeholders. Run `docker compose config -q`, `docker compose up -d --build`, `docker compose run --rm api python -m app.cli ingest`, and `curl --fail http://127.0.0.1:5000/health/ready`; complete the UI login journey at `http://127.0.0.1:5000/`. Run `bash deploy/local/backup.sh`, then restore only from a dump that may safely replace the current graph with `bash deploy/local/restore.sh <dump-path>` and type the exact confirmation requested. Do not copy over an existing `.env` or use a volume-removal command. The active `.env` and any Docker volumes were not modified here.

### Phase 12
- **Status:** Implementation complete locally on `phase-12-ci-cd`, stacked on Phase 11 commit `d8829df`; uncommitted pending review.
- **Implemented:** CI split into lint, unit/coverage, real-service integration, contract, Compose/Playwright E2E, security and no-push image-build jobs; service/repository coverage regression gate; full-SHA action pin policy; failure-only test and Playwright trace artifacts; optional manual OIDC S3 packaging workflow with packaging concurrency, Step Summary provenance, and gated by `AWS_DEMO_ENABLED=true`; local workflow contract checks and a detect-secrets baseline.
- **Coverage baseline:** Captured with Python 3.11.14 and `pytest -q -m "not integration and not e2e"`: services 85.44% (358/419 statements), repositories 41.78% (61/146 statements). The CI gate rejects a decrease in either group and does not impose a new coverage target.
- **Branch protection recommendation:** Require `lint`, `unit`, `integration`, `contract`, `e2e`, `security`, and `image` on `main`; do not require the optional AWS packaging workflow.
- **Local checks:** `ruff check app tests scripts benchmarks optional_integrations` passed; Ruff format check passed for 68 Python files; `pytest -q -m "not integration and not e2e"` passed (163 passed, 9 skipped, 36 deselected); the coverage gate passed at the recorded 85.44% services / 41.78% repositories baseline; `scripts/export_openapi.py --check` passed; `pip-audit -r requirements.txt` passed with no known vulnerabilities; actionlint 1.7.12 passed on both workflows; detect-secrets hook passed against tracked and new Phase 12 paths; `git diff --check` passed. A deliberate failing pytest and a fake AWS-key scan both returned nonzero on a disposable local branch; that branch and scratch files were removed.
- **Unverified:** GitHub Actions jobs and PR execution require the Phase 12 review/commit and remote branch publication. Docker engine access remains unavailable under the existing environment restriction; therefore CI E2E, integration-service and image-build jobs were not run locally. ShellCheck is not installed locally; GitHub-hosted lint job invokes it for active scripts. The optional AWS packaging workflow is intentionally gated off and remains unverified beyond actionlint and static tests.
