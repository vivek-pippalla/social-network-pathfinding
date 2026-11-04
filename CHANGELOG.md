# Changelog

All notable changes to the Social Network Pathfinding project since the `pre-rebuild` baseline.

## [v1.0.0] - Unreleased / Rebuild Milestone

### Security & Authentication
- **Argon2id Password Storage:** Replaced legacy insecure hashing with `argon2-cffi` using pinned memory, time, and parallelism parameters.
- **JWT Ephemeral Tokens:** Replaced unverified tokens with standard HS256 JSON Web Tokens (`PyJWT`) with a 30-minute lifespan, subject DB verification, and timezone-aware UTC timestamps.
- **Credential Separation:** Segregated user authentication credentials into dedicated private `(:Account)` nodes that own public `(:User)` nodes; private emails and password hashes are structurally inaccessible to graph traversals and public user endpoints.
- **Strict Input Validation:** Enforced Pydantic v2 schemas across all payloads, including RFC-compliant email validation, normalized lowercase emails, and password complexity requirements distinct from user identity.
- **Abuse Prevention & Fail-Closed Security:** Implemented atomic Redis-backed fixed-window rate limiting on registration, login (5 requests/minute), and search (30 requests/minute). Authentication endpoints fail closed (HTTP 503) if Redis is unavailable.
- **Container Hardening:** Updated runtime image to Debian Bookworm patch release; removed build packaging tools (`pip`, `setuptools`, `wheel`) and `curl`; configured non-root system user (`10001:10001`).

### Graph Architecture & Pathfinding
- **Constraint-Enforced Schema:** Created uniqueness constraints on `User.id` and `Account.email_normalized`, plus text indexing on `User.name_lower`, replacing unindexed label scans with `UniqueIndexSeek` lookups.
- **Bounded Shortest Path:** Implemented parameterized Cypher queries bounded by `MAX_PATH_DEPTH=6` using Index-Free Adjacency (IFA), preventing unbounded graph traversal denial-of-service.
- **Canonical Edge Direction:** Normalized undirected relationship creation using sorted endpoint tuples (`low_id -> high_id`), preventing inverted or duplicate relationships under concurrent requests.
- **Negative & Invalidation Caching:** Integrated $O(1)$ version-based Redis cache invalidation on friendship mutations; added negative caching with a 60-second TTL for unreachable pairs.
- **Path Reorientation:** Ensured cached path results reorient start and end nodes dynamically to match the caller's query orientation.

### Ingestion Pipeline
- **Checksum Integrity Verification:** Added SHA-256 pre-verification for Stanford SNAP dataset archives; corrupted files are halted before opening database sessions or modifying schema/graph state.
- **Resilient Parsing:** Sanitized edge list parsing to filter malformed lines, non-conforming IDs, self-loops, and duplicate edges.
- **Preservation of Registered Users:** Ingestion reset isolates `(:User {source: 'snap'})` deletions, preserving registered application users and friendships across ingestion runs.

### Operational Reliability & Deployment
- **Standardized Error Envelopes:** Unified API error responses under `{ "error": { "code", "message", "request_id", "details" } }`.
- **Deep Health Probes:** Added `/health/ready` verifying live connectivity to Neo4j and Redis; degraded mode gracefully handles Redis downtime for graph queries.
- **Local Deployment & Automated Rollback:** Authored `deploy/local/deploy.sh` with automated container replacement and rollback on readiness probe failures.
- **Offline Backup & Restore:** Implemented offline database dump and restore scripts via `neo4j-admin database load`.

### Testing & Verification
- **Multi-Layer Test Suite:** 177 unit/contract tests and 36 live-service integration tests against real Neo4j 5.12 and Redis 7 containers.
- **Independent BFS Oracle:** Verified Cypher shortest-path hop counts against an independent Python BFS implementation.
- **Verified Latency Benchmarks:** Recorded local performance on the SNAP dataset (18.6ms cold Neo4j, 14.9ms warm Redis cache).

