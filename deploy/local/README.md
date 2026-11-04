# Local Docker deployment

The local Docker Compose stack is the supported deployment target. It needs no AWS
account or AWS tooling. Docker Compose starts the API, Neo4j and Redis; the default
development override publishes their ports on `127.0.0.1` only. Prometheus and
Grafana are available with the `monitoring` profile. The prod-like file adds Caddy
and leaves the API and database ports unpublished.

## First run

On a fresh clone, copy `.env.example` to `.env` and replace the `SECRET_KEY`,
`NEO4J_PASSWORD` and `REDIS_PASSWORD` placeholders with independent random
hexadecimal values. For example, run `openssl rand -hex 32` for the app secret and
`openssl rand -hex 24` for each database password, then paste the outputs into the
matching `.env` entries. Keep `.env` private and do not overwrite an existing
`.env` when working in a repository that already has local configuration.

```sh
docker compose config -q
docker compose up -d --build
docker compose ps
curl --fail http://127.0.0.1:5000/health/ready
docker compose run --rm api python -m app.cli ingest
```

The first ingestion downloads the SNAP archive directly from Stanford, verifies
its pinned SHA-256, and then writes it to Neo4j. The archive is excluded from Git
and the Docker build context because SNAP does not provide a clear dataset
redistribution license. The API is available at `http://127.0.0.1:5000/`.

To enable monitoring, set non-placeholder `GRAFANA_ADMIN_USER` and
`GRAFANA_ADMIN_PASSWORD` values in `.env`, then run
`docker compose --profile monitoring up -d`. Prometheus and Grafana bind only to
loopback (`127.0.0.1:9090` and `127.0.0.1:3000`).

## Prod-like Compose

The prod-like stack is selected explicitly so Docker Compose does not load the
development override:

```sh
docker compose -f docker-compose.yml -f docker-compose.prod.yml --profile edge config -q
docker compose -f docker-compose.yml -f docker-compose.prod.yml --profile edge up -d --build
COMPOSE_FILE=docker-compose.yml:docker-compose.prod.yml COMPOSE_PROFILES=edge SITE_ADDRESS=:80 BASE_URL=http://localhost bash deploy/local/deploy.sh
```

Set `SITE_ADDRESS=:80` for plain HTTP on a local host or IP. A domain or
`localhost` site address lets Caddy manage HTTPS; use a browser or `curl` trust
store that accepts the certificate. `BASE_URL` can override the URL checked by
the deploy script. Only Caddy publishes ports in this configuration. Caddy
returns 404 for `/metrics`; Prometheus scrapes that endpoint over the private
Compose network. `/docs` and `/openapi.json` are disabled.

The API trusts forwarded headers only from `TRUSTED_PROXY_ADDRESSES`. The prod-like
Compose file defaults this to the dedicated `edge` network subnet, where Caddy is
the only service. If that subnet overlaps a local network, choose another
`EDGE_NETWORK_SUBNET` and set `TRUSTED_PROXY_ADDRESSES` to the same subnet.

`deploy.sh` builds the API image, starts the selected Compose stack, and checks
`/health/ready`. If readiness fails after an upgrade, it starts the previously
running API image and checks it. A failed deployment exits non-zero even when
rollback succeeds. On a first install it stops the failed API and leaves database
volumes intact.

## Backup and restore

`bash deploy/local/backup.sh [output-directory]` stops the API and Neo4j briefly,
uses `neo4j-admin database dump neo4j --to-path=<directory>` against an offline
database, copies the dump to the chosen host directory, then starts Neo4j and the
API again. This is an offline Community Edition dump, so it includes the
application's `neo4j` database but not Neo4j DBMS users or roles; keep the
operator's `.env` separately.

Restore is destructive to the current `neo4j` database and always prompts for the
exact confirmation `RESTORE <dump-filename>`:

```sh
bash deploy/local/restore.sh ./backups/neo4j-<timestamp>.dump
```

The restore script stages the selected dump under the required `neo4j.dump` name,
stops the API and database, and runs
`neo4j-admin database load --from-path=/restore neo4j --overwrite-destination=true`.
It starts the database and API afterward. Do not restore into a database whose
current data you need to keep; make a backup first.

The command forms above were checked against Neo4j's official [offline Docker
dump/load guide](https://neo4j.com/docs/operations-manual/current/docker/dump-load/)
and [dump](https://neo4j.com/docs/operations-manual/current/backup-restore/offline-backup/)
and [load](https://neo4j.com/docs/operations-manual/current/backup-restore/restore-dump/)
reference pages. The current Compose pin remains Neo4j `5.12.0`. Neo4j's release
archive lists `5.26.32` (released 9 October 2026) as the latest 5.x release; that
is a proposed pin only. A version change needs a separate approval and a tested
backup/restore migration. These are the current manual pages, not version-locked
5.12.0 documentation; the exact commands against the pinned image remain
unverified until the image can be run locally.

## Operator settings

- `WEB_CONCURRENCY` defaults to 2. `NEO4J_HEAP_INITIAL`, `NEO4J_HEAP_MAX` and
  `NEO4J_PAGECACHE` set Neo4j memory sizes (defaults `512M`, `1G` and `512M`).
  Adjust them to fit the host.
- Redis is a non-persistent cache, requires `REDIS_PASSWORD`, and uses an LRU
  eviction policy. No AOF data is retained.
- `COMPOSE_PROFILES=edge` enables Caddy when the prod-like Compose files are
  selected; `COMPOSE_PROFILES=monitoring` enables Prometheus and Grafana.
- `docker compose down` preserves named database and backup volumes. Do not add
  `-v` unless you intend to delete them.
