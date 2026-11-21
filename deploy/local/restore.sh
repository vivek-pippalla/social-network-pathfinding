#!/usr/bin/env bash
set -Eeuo pipefail

if [[ $# -ne 1 || ! -f $1 || ! -s $1 || $1 != *.dump ]]; then
    printf 'Usage: %s PATH_TO_NEO4J_DUMP\n' "$0" >&2
    exit 2
fi
dump_file=$(cd "$(dirname "$1")" && pwd)/$(basename "$1")
dump_name=$(basename "$dump_file")
for tool in sha256sum python3 grep; do
    command -v "$tool" >/dev/null 2>&1 || { printf 'ERROR: Required command not found: %s\n' "$tool" >&2; exit 2; }
done
checksum_file=${dump_file}.sha256
metadata_file=${dump_file}.metadata.json
[[ -s $checksum_file && -s $metadata_file ]] || { echo 'ERROR: Dump requires non-empty SHA-256 and version metadata sidecars.' >&2; exit 1; }
expected_sha=$(awk "NR == 1 {print \$1}" "$checksum_file")
actual_sha=$(sha256sum "$dump_file" | cut -d ' ' -f 1)
[[ $expected_sha =~ ^[a-fA-F0-9]{64}$ && $actual_sha == "$expected_sha" ]] || { echo 'ERROR: Dump SHA-256 does not match its sidecar.' >&2; exit 1; }
metadata_version=$(python3 - "$metadata_file" "$dump_name" "$actual_sha" <<'PY'
import json
import re
import sys

try:
    with open(sys.argv[1], encoding="utf-8") as metadata_file:
        metadata = json.load(metadata_file)
    if metadata.get("database") != "neo4j":
        raise ValueError
    if metadata.get("dump") != sys.argv[2] or metadata.get("sha256") != sys.argv[3]:
        raise ValueError
    version = metadata.get("neo4j_version")
    if not isinstance(version, str) or not re.fullmatch(r"\d+\.\d+\.\d+", version):
        raise ValueError
    print(version)
except Exception:
    sys.exit(1)
PY
) || { echo 'ERROR: Dump metadata is invalid or does not match this dump.' >&2; exit 1; }

if ! command -v docker >/dev/null 2>&1; then
    printf 'ERROR: Docker CLI is not installed.\n' >&2; exit 2
fi
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

target_version_output=$(compose run --rm --no-deps --entrypoint neo4j-admin neo4j --version) || { echo 'ERROR: Could not query configured Neo4j version; database was not stopped.' >&2; exit 1; }
target_version=$( { printf '%s\n' "$target_version_output" | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -n 1; } || true)
[[ -n $target_version ]] || { echo 'ERROR: Could not determine configured Neo4j version; database was not stopped.' >&2; exit 1; }
[[ $metadata_version == "$target_version" ]] || {
    printf 'ERROR: Backup Neo4j version %s does not exactly match configured target version %s; database was not stopped.\n' "$metadata_version" "$target_version" >&2
    exit 1
}

confirmation_text="RESTORE APPLICATION neo4j FROM ${dump_name}"
echo 'TARGET: configured application Compose database neo4j (not an isolated/test database).'
echo 'CONSEQUENCE: all current graph data in that database will be overwritten; no automatic rollback is available.'
echo "SOURCE: ${dump_file} (Neo4j ${metadata_version}; SHA-256 verified)"
if [[ ${FORCE_RESTORE:-} == "$confirmation_text" ]]; then
    echo 'Explicit target confirmation received.'
else
    if [[ ! -t 0 ]]; then echo "ERROR: Interactive confirmation required; expected: ${confirmation_text}" >&2; exit 1; fi
    read -r -p "Type '${confirmation_text}' to continue: " confirmation
    [[ $confirmation == "$confirmation_text" ]] || { echo 'Restore cancelled.' >&2; exit 1; }
fi

staging_dir=$(mktemp -d)
services_stopped=false
restore_state='Validation succeeded; services have not been stopped.'
load_started=false
load_succeeded=false
finish() {
    local result=$?
    trap - EXIT
    if rm -rf -- "$staging_dir"; then
        echo "Cleanup state: staging directory removed ($staging_dir)."
    else
        result=1
        printf 'Cleanup state: FAILED to remove staging directory %s.\n' "$staging_dir" >&2
    fi
    if [[ $services_stopped == true ]]; then
        if compose up --detach --wait neo4j api; then
            if [[ $load_succeeded == true ]]; then
                restore_state='Database load succeeded; services restarted successfully.'
            elif [[ $load_started == true ]]; then
                restore_state='Database load started but failed; services restarted successfully; database state requires operator validation.'
            else
                restore_state='Services stopped but database load did not start; services restarted successfully.'
            fi
        else
            result=1
            restore_state+=" Service restart failed; manual operator recovery is required."
        fi
    fi
    printf 'Restore state: %s\n' "$restore_state" >&2
    [[ $load_succeeded != true ]] || printf 'Rollback: none; no rollback capability is claimed.\n' >&2
    exit "$result"
}
trap finish EXIT

cp -- "$dump_file" "${staging_dir}/neo4j.dump"
services_stopped=true
restore_state='Services stopped; database load did not start.'
compose stop api neo4j
load_started=true
restore_state='Database load started.'
compose run --rm --no-deps --volume "${staging_dir}:/restore:ro" \
    --entrypoint neo4j-admin neo4j \
    database load --from-path=/restore neo4j --overwrite-destination=true
load_succeeded=true
restore_state='Database load succeeded; services are restarting.'
compose up --detach --wait neo4j api
services_stopped=false
printf 'Restore completed from %s\n' "$dump_file"
restore_state='Database load succeeded; services restarted successfully.'
