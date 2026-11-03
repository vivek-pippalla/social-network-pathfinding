# Social Network Pathfinding — Implementation Status

> Record verified work only. Do not mark work complete based on intention or unverified agent claims.

## Project controls
- **Master plan:** `BUILD_PLAN.md` — Social Network Pathfinding: Reconstruction Blueprint
- **Working branch:** phase-6-redis-caching-invalidation (stacked from Phase 5; main unchanged)
- **Protected baseline:** `main` — do not modify directly
- **Current phase:** Phase 6 — Redis caching and invalidation
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
| Phase 6: Redis caching and invalidation | Implemented locally; real-service verification deferred | Cache consistency guarantee and local checks recorded below; real Neo4j/Redis behavior remains unverified |

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
