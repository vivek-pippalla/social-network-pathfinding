#!/usr/bin/env bash
set -Eeuo pipefail

output_dir=${1:-${BACKUP_DIR:-./backups}}
mkdir -p -- "$output_dir"
output_dir=$(cd "$output_dir" && pwd)

# Select one Docker invocation path before doing work. DOCKER_SUDO accepts
# auto (default), always, or never. No socket permissions are changed.
if ! command -v docker >/dev/null 2>&1; then
    printf 'ERROR: Docker CLI is not installed.\n' >&2; exit 2
fi
command -v sha256sum >/dev/null 2>&1 || { echo 'ERROR: sha256sum is required.' >&2; exit 2; }
command -v python3 >/dev/null 2>&1 || { echo 'ERROR: python3 is required to write backup metadata.' >&2; exit 2; }
command -v grep >/dev/null 2>&1 || { echo 'ERROR: grep is required.' >&2; exit 2; }
case ${DOCKER_SUDO:-auto} in
    never)
        docker info >/dev/null 2>&1 || { echo 'ERROR: Docker is inaccessible with DOCKER_SUDO=never.' >&2; exit 2; }
        docker_cmd=(docker) ;;
    always)
        if ! command -v sudo >/dev/null 2>&1 || ! sudo -n docker info >/dev/null 2>&1; then
            echo 'ERROR: DOCKER_SUDO=always requires usable non-interactive sudo access to Docker.' >&2
            exit 2
        fi
        docker_cmd=(sudo -n docker) ;;
    auto)
        if docker info >/dev/null 2>&1; then docker_cmd=(docker)
        elif command -v sudo >/dev/null 2>&1 && sudo -n docker info >/dev/null 2>&1; then docker_cmd=(sudo -n docker)
        else echo 'ERROR: Docker daemon is unavailable or inaccessible; no usable sudo fallback was found.' >&2; exit 2; fi ;;
    *) printf 'ERROR: DOCKER_SUDO must be auto, always, or never.\n' >&2; exit 2 ;;
esac
compose() { "${docker_cmd[@]}" compose "$@"; }
docker_cli() { "${docker_cmd[@]}" "$@"; }

for service in neo4j api; do
    container_id=$(compose ps --quiet "$service") || { printf 'ERROR: Could not inspect %s service state.\n' "$service" >&2; exit 1; }
    [[ -n $container_id ]] || { printf 'ERROR: %s service is not running; start the stack before backing up.\n' "$service" >&2; exit 1; }
    health=$(docker_cli inspect --format '{{.State.Health.Status}}' "$container_id" 2>/dev/null || true)
    [[ $health == healthy ]] || { printf 'ERROR: %s service is not healthy (%s); refusing backup.\n' "$service" "${health:-unknown}" >&2; exit 1; }
done
neo4j_version_output=$(compose run --rm --no-deps --entrypoint neo4j-admin neo4j --version) || { echo 'ERROR: Could not run neo4j-admin to determine the dump tool version.' >&2; exit 1; }
neo4j_version=$( { printf '%s\n' "$neo4j_version_output" | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -n 1; } || true)
[[ -n $neo4j_version ]] || { echo 'ERROR: Could not determine the Neo4j dump tool version.' >&2; exit 1; }

timestamp=$(date -u +%Y%m%dT%H%M%SZ)
backup_id="${timestamp}-$$"
helper="social-network-backup-${backup_id}"
destination="${output_dir}/neo4j-${backup_id}.dump"
[[ ! -e $destination ]] || { echo 'ERROR: Backup destination already exists; refusing to overwrite it.' >&2; exit 1; }
services_stopped=false
helper_created=false
backup_temp_cleaned=false

finish() {
    local result=$?
    trap - EXIT
    if [[ $helper_created == true ]]; then docker_cli rm -f "$helper" >/dev/null 2>&1 || result=1; fi
    if [[ $services_stopped == true ]]; then
        if [[ $backup_temp_cleaned == false ]]; then
            # shellcheck disable=SC2016  # $BACKUP_ID expands inside the container
            compose run --rm --no-deps -e "BACKUP_ID=$backup_id" --entrypoint sh neo4j \
                -ec 'rm -rf -- "/backups/$BACKUP_ID"' || result=1
        fi
        compose up --detach --wait neo4j api || result=1
    fi
    exit "$result"
}
trap finish EXIT

services_stopped=true
compose stop api neo4j
# shellcheck disable=SC2016  # $BACKUP_ID expands inside the container
compose run --rm --no-deps -e "BACKUP_ID=$backup_id" --entrypoint sh neo4j \
    -ec 'mkdir -p "/backups/$BACKUP_ID"'
helper_created=true
compose run --no-deps --name "$helper" --entrypoint neo4j-admin neo4j \
    database dump neo4j "--to-path=/backups/${backup_id}"
docker_cli cp "${helper}:/backups/${backup_id}/neo4j.dump" "$destination"
docker_cli rm "$helper" >/dev/null
helper_created=false
if [[ ! -s $destination ]]; then printf 'ERROR: Neo4j produced an empty or missing dump.\n' >&2; exit 1; fi
sha256sum "$destination" > "${destination}.sha256"
dump_sha256=$(cut -d ' ' -f 1 "${destination}.sha256")
python3 - "$destination" "$neo4j_version" "$dump_sha256" <<'PY'
import json
import pathlib
import sys

dump_path, neo4j_version, sha256 = sys.argv[1:]
metadata = {
    "database": "neo4j",
    "dump": pathlib.Path(dump_path).name,
    "neo4j_version": neo4j_version,
    "sha256": sha256,
}
pathlib.Path(dump_path + ".metadata.json").write_text(
    json.dumps(metadata, sort_keys=True) + "\n", encoding="utf-8"
)
PY
# shellcheck disable=SC2016  # $BACKUP_ID expands inside the container
compose run --rm --no-deps -e "BACKUP_ID=$backup_id" --entrypoint sh neo4j \
    -ec 'rm -rf -- "/backups/$BACKUP_ID"'
backup_temp_cleaned=true

compose up --detach --wait neo4j api
services_stopped=false
printf 'Backup created: %s\nBACKUP_PATH=%s\nNEO4J_VERSION=%s\n' "$destination" "$destination" "$neo4j_version"
