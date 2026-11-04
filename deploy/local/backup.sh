#!/usr/bin/env bash
set -Eeuo pipefail

output_dir=${1:-./backups}
mkdir -p "$output_dir"
timestamp=$(date -u +%Y%m%dT%H%M%SZ)
backup_id="${timestamp}-$$"
helper="social-network-backup-${backup_id}"
destination="${output_dir%/}/neo4j-${backup_id}.dump"
services_stopped=false
helper_created=false
backup_temp_cleaned=false

finish() {
    local result=$?
    trap - EXIT
    if [[ "$helper_created" == true ]]; then
        docker rm -f "$helper" >/dev/null 2>&1 || result=1
    fi
    if [[ "$services_stopped" == true ]]; then
        if [[ "$backup_temp_cleaned" == false ]]; then
            docker compose run --rm --no-deps -e "BACKUP_ID=${backup_id}" \
                --entrypoint sh neo4j \
                -ec 'rm -rf -- "/backups/$BACKUP_ID"' || result=1
        fi
        docker compose up --detach neo4j || result=1
        docker compose up --detach api || result=1
    fi
    exit "$result"
}
trap finish EXIT

services_stopped=true
docker compose stop api neo4j

# Community edition dump/load is offline. The named backup volume is shared
# with the Neo4j service so the admin command runs as the image's neo4j user.
docker compose run --rm --no-deps -e "BACKUP_ID=${backup_id}" \
    --entrypoint sh neo4j -ec 'mkdir -p "/backups/$BACKUP_ID"'
helper_created=true
docker compose run --no-deps --name "$helper" --entrypoint neo4j-admin neo4j \
    database dump neo4j "--to-path=/backups/${backup_id}"
docker cp "${helper}:/backups/${backup_id}/neo4j.dump" "$destination"
docker rm "$helper" >/dev/null
helper_created=false
docker compose run --rm --no-deps -e "BACKUP_ID=${backup_id}" \
    --entrypoint sh neo4j -ec 'rm -rf -- "/backups/$BACKUP_ID"'
backup_temp_cleaned=true

docker compose up --detach neo4j
docker compose up --detach api
services_stopped=false
printf 'Backup created: %s\n' "$destination"
