#!/usr/bin/env bash
set -Eeuo pipefail

if [[ $# -ne 1 || ! -f "$1" ]]; then
    printf 'Usage: %s PATH_TO_NEO4J_DUMP\n' "$0" >&2
    exit 2
fi

dump_file=$(cd "$(dirname "$1")" && pwd)/$(basename "$1")
dump_name=$(basename "$dump_file")
read -r -p "This replaces the Neo4j database. Type RESTORE ${dump_name} to continue: " confirmation
if [[ "$confirmation" != "RESTORE ${dump_name}" ]]; then
    printf 'Restore cancelled.\n' >&2
    exit 1
fi

staging_dir=$(mktemp -d)
services_stopped=false

finish() {
    local result=$?
    trap - EXIT
    rm -rf -- "$staging_dir"
    if [[ "$services_stopped" == true ]]; then
        docker compose up --detach neo4j || result=1
        docker compose up --detach api || result=1
    fi
    exit "$result"
}
trap finish EXIT

# The load command selects the database by the conventional filename.
cp -- "$dump_file" "${staging_dir}/neo4j.dump"
services_stopped=true
docker compose stop api neo4j

# Neo4j Community database load must run while the DBMS is offline.
docker compose run --rm --no-deps \
    --volume "${staging_dir}:/restore:ro" \
    --entrypoint neo4j-admin neo4j \
    database load --from-path=/restore neo4j --overwrite-destination=true

docker compose up --detach neo4j
docker compose up --detach api
services_stopped=false
printf 'Restore completed from %s\n' "$dump_file"
