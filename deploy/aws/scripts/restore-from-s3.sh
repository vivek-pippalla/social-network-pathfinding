#!/usr/bin/env bash
# ==============================================================================
# deploy/aws/scripts/restore-from-s3.sh — Download & Restore Neo4j Dump from S3
# Verifies SHA-256 integrity before touching Neo4j; requires explicit typed confirmation.
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../../.." && pwd)"
LOCAL_RESTORE_SCRIPT="${PROJECT_ROOT}/deploy/local/restore.sh"

cd "${PROJECT_ROOT}"

if [ "$#" -ne 1 ]; then
    echo "Usage: $0 <TIMESTAMP_OR_BACKUP_PREFIX>" >&2
    echo "Example: $0 20261104T153618Z" >&2
    exit 1
fi

BACKUP_TARGET="$1"

# Load BACKUP_BUCKET from environment or .env
if [ -z "${BACKUP_BUCKET:-}" ] && [ -f .env ]; then
    BACKUP_BUCKET=$(grep -E '^BACKUP_BUCKET=' .env | cut -d '=' -f2- | tr -d ' "' || true)
fi

if [ -z "${BACKUP_BUCKET:-}" ] || [ "${BACKUP_BUCKET}" = "<BUCKET_NAME>" ]; then
    echo "ERROR: BACKUP_BUCKET is not set or contains placeholder value." >&2
    exit 1
fi

echo "=============================================================================="
echo " WARNING: RESTORING A DATABASE OVERWRITES ALL CURRENT NEO4J GRAPH DATA!"
echo " Target backup prefix: s3://${BACKUP_BUCKET}/backups/${BACKUP_TARGET}/"
echo "=============================================================================="

# Prompt for explicit typed confirmation unless running in non-interactive CI mode with FORCE_RESTORE=RESTORE
if [ "${FORCE_RESTORE:-}" != "RESTORE" ]; then
    read -r -p "Type 'RESTORE' to confirm destructive database overwrite: " CONFIRMATION
    if [ "${CONFIRMATION}" != "RESTORE" ]; then
        echo "Aborted. Confirmation did not match 'RESTORE'." >&2
        exit 1
    fi
fi

S3_SOURCE_DIR="s3://${BACKUP_BUCKET}/backups/${BACKUP_TARGET}"
DOWNLOAD_DIR=$(mktemp -d)
trap 'rm -rf "${DOWNLOAD_DIR}"' EXIT

echo "=== Step 1: Downloading backup files from S3 ==="
aws s3 cp "${S3_SOURCE_DIR}" "${DOWNLOAD_DIR}" --recursive

DOWNLOADED_DUMP=$(find "${DOWNLOAD_DIR}" -name "*.dump" -type f | head -n 1)
DOWNLOADED_SHA=$(find "${DOWNLOAD_DIR}" -name "*.sha256" -type f | head -n 1)

if [ -z "${DOWNLOADED_DUMP}" ] || [ ! -f "${DOWNLOADED_DUMP}" ]; then
    echo "ERROR: No .dump file found in ${S3_SOURCE_DIR}." >&2
    exit 1
fi

if [ -z "${DOWNLOADED_SHA}" ] || [ ! -f "${DOWNLOADED_SHA}" ]; then
    echo "ERROR: No .sha256 file found in ${S3_SOURCE_DIR}." >&2
    exit 1
fi

echo "=== Step 2: Verifying checksum integrity before restore ==="
EXPECTED_SHA=$(cut -d ' ' -f 1 "${DOWNLOADED_SHA}")

if command -v sha256sum &>/dev/null; then
    ACTUAL_SHA=$(sha256sum "${DOWNLOADED_DUMP}" | cut -d ' ' -f 1)
elif command -v shasum &>/dev/null; then
    ACTUAL_SHA=$(shasum -a 256 "${DOWNLOADED_DUMP}" | cut -d ' ' -f 1)
else
    echo "ERROR: Neither sha256sum nor shasum available." >&2
    exit 1
fi

if [ "${EXPECTED_SHA}" != "${ACTUAL_SHA}" ]; then
    echo "ERROR: SHA-256 verification failed! Refusing to load corrupted dump." >&2
    echo "Expected: ${EXPECTED_SHA}" >&2
    echo "Actual:   ${ACTUAL_SHA}" >&2
    exit 1
fi
echo "Integrity verified: SHA-256 checksum matches."

echo "=== Step 3: Invoking local restore script ==="
if [ ! -x "${LOCAL_RESTORE_SCRIPT}" ]; then
    chmod +x "${LOCAL_RESTORE_SCRIPT}" 2>/dev/null || true
fi

# Copy verified dump to a local path that survives the trap cleanup
STAGE_RESTORE_PATH="${PROJECT_ROOT}/backups/restore_$(basename "${DOWNLOADED_DUMP}")"
mkdir -p "${PROJECT_ROOT}/backups"
cp "${DOWNLOADED_DUMP}" "${STAGE_RESTORE_PATH}"

printf "RESTORE %s\n" "$(basename "${STAGE_RESTORE_PATH}")" | "${LOCAL_RESTORE_SCRIPT}" "${STAGE_RESTORE_PATH}"

rm -f "${STAGE_RESTORE_PATH}"
echo "SUCCESS: Database restored successfully from ${S3_SOURCE_DIR}"
