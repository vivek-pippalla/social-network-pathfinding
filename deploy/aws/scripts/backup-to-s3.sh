#!/usr/bin/env bash
# ==============================================================================
# deploy/aws/scripts/backup-to-s3.sh — Upload Neo4j Backup Dump to Amazon S3
# Runs local backup, computes SHA-256 digest, uploads to S3, and verifies digest.
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../../.." && pwd)"
LOCAL_BACKUP_SCRIPT="${PROJECT_ROOT}/deploy/local/backup.sh"

cd "${PROJECT_ROOT}"

# Load BACKUP_BUCKET from environment or .env
if [ -z "${BACKUP_BUCKET:-}" ] && [ -f .env ]; then
    BACKUP_BUCKET=$(grep -E '^BACKUP_BUCKET=' .env | cut -d '=' -f2- | tr -d ' "' || true)
fi

if [ -z "${BACKUP_BUCKET:-}" ] || [ "${BACKUP_BUCKET}" = "<BUCKET_NAME>" ]; then
    echo "ERROR: BACKUP_BUCKET is not set or contains placeholder value." >&2
    echo "Set BACKUP_BUCKET in your environment or .env file." >&2
    exit 1
fi

echo "=== Step 1: Executing local Neo4j database backup ==="
if [ ! -x "${LOCAL_BACKUP_SCRIPT}" ]; then
    chmod +x "${LOCAL_BACKUP_SCRIPT}" 2>/dev/null || true
fi

# Capture output of local backup to find the created dump
BACKUP_OUTPUT=$("${LOCAL_BACKUP_SCRIPT}")
echo "${BACKUP_OUTPUT}"

# Locate the most recent dump file in ./backups
LATEST_DUMP=$(find "${PROJECT_ROOT}/backups" -name "neo4j-*.dump" -type f 2>/dev/null | sort | tail -n 1)

if [ -z "${LATEST_DUMP}" ] || [ ! -f "${LATEST_DUMP}" ]; then
    echo "ERROR: Failed to find generated dump file in ./backups." >&2
    exit 1
fi

DUMP_FILENAME=$(basename "${LATEST_DUMP}")
TIMESTAMP=$(echo "${DUMP_FILENAME}" | sed -E 's/^neo4j-([0-9]{8}T[0-9]{6}Z).*/\1/')
if [ -z "${TIMESTAMP}" ] || [ "${TIMESTAMP}" = "${DUMP_FILENAME}" ]; then
    TIMESTAMP=$(date -u +"%Y%m%dT%H%M%SZ")
fi

echo "=== Step 2: Generating SHA-256 digest ==="
SHA256_FILE="${LATEST_DUMP}.sha256"
if command -v sha256sum &>/dev/null; then
    sha256sum "${LATEST_DUMP}" > "${SHA256_FILE}"
elif command -v shasum &>/dev/null; then
    shasum -a 256 "${LATEST_DUMP}" > "${SHA256_FILE}"
else
    echo "ERROR: Neither sha256sum nor shasum available." >&2
    exit 1
fi
LOCAL_CHECKSUM=$(cut -d ' ' -f 1 "${SHA256_FILE}")
echo "Local Checksum: ${LOCAL_CHECKSUM}"

DEST_PREFIX="s3://${BACKUP_BUCKET}/backups/${TIMESTAMP}"

echo "=== Step 3: Uploading to Amazon S3 (${DEST_PREFIX}) ==="
aws s3 cp "${LATEST_DUMP}" "${DEST_PREFIX}/${DUMP_FILENAME}"
aws s3 cp "${SHA256_FILE}" "${DEST_PREFIX}/${DUMP_FILENAME}.sha256"

echo "=== Step 4: Verifying S3 upload integrity ==="
REMOTE_SHA256_FILE=$(mktemp)
trap 'rm -f "${REMOTE_SHA256_FILE}"' EXIT

aws s3 cp "${DEST_PREFIX}/${DUMP_FILENAME}.sha256" "${REMOTE_SHA256_FILE}"
REMOTE_CHECKSUM=$(cut -d ' ' -f 1 "${REMOTE_SHA256_FILE}")

if [ "${LOCAL_CHECKSUM}" != "${REMOTE_CHECKSUM}" ]; then
    echo "ERROR: Checksum mismatch between local file and uploaded S3 checksum!" >&2
    echo "Local:  ${LOCAL_CHECKSUM}" >&2
    echo "Remote: ${REMOTE_CHECKSUM}" >&2
    exit 1
fi

echo "SUCCESS: Backup verified and archived at ${DEST_PREFIX}/${DUMP_FILENAME}"
