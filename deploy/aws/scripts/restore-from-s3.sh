#!/usr/bin/env bash
# Restore one verified backup into the configured application Compose database.
set -Eeuo pipefail
SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
PROJECT_ROOT=$(cd "$SCRIPT_DIR/../../.." && pwd)
LOCAL_RESTORE_SCRIPT=$PROJECT_ROOT/deploy/local/restore.sh
cd "$PROJECT_ROOT"

if [[ $# != 1 ]]; then echo "Usage: $0 <UTC_TIMESTAMP>" >&2; exit 2; fi
BACKUP_TARGET=$1
[[ $BACKUP_TARGET =~ ^[0-9]{8}T[0-9]{6}Z$ ]] || { echo 'ERROR: Target must be a UTC timestamp such as 20261104T153618Z.' >&2; exit 2; }
if [[ -z ${BACKUP_BUCKET:-} && -f .env ]]; then BACKUP_BUCKET=$(sed -n 's/^BACKUP_BUCKET=//p' .env | head -n 1 | tr -d '\r' | sed 's/^"//;s/"$//'); fi
[[ -n ${BACKUP_BUCKET:-} && $BACKUP_BUCKET != '<BUCKET_NAME>' ]] || { echo 'ERROR: Set BACKUP_BUCKET to the configured bucket.' >&2; exit 2; }
[[ $BACKUP_BUCKET =~ ^[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]$ ]] || { echo 'ERROR: BACKUP_BUCKET has an invalid bucket-name format.' >&2; exit 2; }
AWS_REGION=${AWS_REGION:-${AWS_DEFAULT_REGION:-}}
if [[ -z $AWS_REGION && -f .env ]]; then AWS_REGION=$(sed -n 's/^AWS_REGION=//p' .env | head -n 1 | tr -d '\r'); fi
[[ -n $AWS_REGION && $AWS_REGION != '<REGION>' ]] || { echo 'ERROR: Set AWS_REGION or AWS_DEFAULT_REGION.' >&2; exit 2; }
command -v aws >/dev/null 2>&1 || { echo 'ERROR: AWS CLI is not installed.' >&2; exit 2; }
command -v sha256sum >/dev/null 2>&1 || { echo 'ERROR: sha256sum is required.' >&2; exit 2; }
[[ -f $LOCAL_RESTORE_SCRIPT ]] || { echo 'ERROR: Local restore script is missing.' >&2; exit 2; }

S3_BASE="s3://${BACKUP_BUCKET}/backups/${BACKUP_TARGET}"
DUMP_KEYS=$(aws --region "$AWS_REGION" s3api list-objects-v2 --bucket "$BACKUP_BUCKET" \
    --prefix "backups/${BACKUP_TARGET}/" \
    --query "Contents[?ends_with(Key, '.dump')].Key" \
    --output text 2>/dev/null) || {
    echo 'ERROR: Cannot list the requested backup prefix; check AWS credentials, region, and bucket access.' >&2; exit 1;
}
mapfile -t DUMP_KEY_LIST < <(printf '%s\n' "$DUMP_KEYS" | tr '\t' '\n' | sed '/^None$/d;/^$/d')
[[ ${#DUMP_KEY_LIST[@]} == 1 ]] || { printf 'ERROR: Expected exactly one dump under %s; found %s.\n' "$S3_BASE" "${#DUMP_KEY_LIST[@]}" >&2; exit 1; }
DUMP_KEY=${DUMP_KEY_LIST[0]}
[[ $(basename "$DUMP_KEY") =~ ^neo4j-${BACKUP_TARGET}-[0-9]+\.dump$ ]] || { echo 'ERROR: Dump name does not match the requested timestamp.' >&2; exit 1; }
DUMP_FILENAME=$(basename "$DUMP_KEY")
SHA_KEY="${DUMP_KEY}.sha256"
METADATA_KEY="${DUMP_KEY}.metadata.json"
CONFIRMATION_TEXT="RESTORE APPLICATION neo4j FROM ${DUMP_FILENAME}"

DOWNLOAD_DIR=$(mktemp -d) || { echo 'ERROR: Cannot create temporary download directory.' >&2; exit 1; }
DUMP_DOWNLOADED=0
cleanup_download() {
    local result=$?
    trap - EXIT
    if [[ $result -ne 0 && $DUMP_DOWNLOADED == 1 ]]; then
        printf 'Operation failed. Preserving downloaded recovery files:\n  dump: %s\n  checksum: %s\n  metadata: %s\n' "$DUMP_PATH" "$SHA_PATH" "$METADATA_PATH" >&2
    else
        if rm -rf -- "$DOWNLOAD_DIR"; then
            echo "Cleanup state: temporary download directory removed ($DOWNLOAD_DIR)."
        else
            result=1
            printf 'Cleanup state: FAILED to remove temporary directory %s.\n' "$DOWNLOAD_DIR" >&2
        fi
    fi
    exit "$result"
}
trap cleanup_download EXIT
DUMP_PATH=$DOWNLOAD_DIR/$DUMP_FILENAME
SHA_PATH=${DUMP_PATH}.sha256
METADATA_PATH=${DUMP_PATH}.metadata.json
aws --region "$AWS_REGION" s3 cp "s3://${BACKUP_BUCKET}/${DUMP_KEY}" "$DUMP_PATH" --only-show-errors || { echo 'ERROR: Backup dump download failed.' >&2; exit 1; }
DUMP_DOWNLOADED=1
aws --region "$AWS_REGION" s3 cp "s3://${BACKUP_BUCKET}/${SHA_KEY}" "$SHA_PATH" --only-show-errors || { echo 'ERROR: Backup checksum download failed.' >&2; exit 1; }
aws --region "$AWS_REGION" s3 cp "s3://${BACKUP_BUCKET}/${METADATA_KEY}" "$METADATA_PATH" --only-show-errors || { echo 'ERROR: Backup version metadata download failed; legacy backups without metadata cannot be safely restored by this script.' >&2; exit 1; }
[[ -s $DUMP_PATH && -s $SHA_PATH && -s $METADATA_PATH ]] || { echo 'ERROR: Downloaded dump or required sidecar is missing/empty.' >&2; exit 1; }
EXPECTED_SHA=$(awk 'NR == 1 {print $1}' "$SHA_PATH")
ACTUAL_SHA=$(sha256sum "$DUMP_PATH" | cut -d ' ' -f 1)
[[ $EXPECTED_SHA =~ ^[a-fA-F0-9]{64}$ && $EXPECTED_SHA == "$ACTUAL_SHA" ]] || { echo 'ERROR: SHA-256 verification failed; database was not staged or restored.' >&2; exit 1; }
echo 'Backup SHA-256 verified before staging.'

echo 'TARGET: configured application Compose database neo4j (not an isolated/test database).'
echo 'CONSEQUENCE: all current graph data in that database will be overwritten; no automatic rollback is available.'
echo "SOURCE: s3://${BACKUP_BUCKET}/${DUMP_KEY} (dump and sidecars downloaded; checksum verified)"
if [[ ${FORCE_RESTORE:-} == "$CONFIRMATION_TEXT" ]]; then
    echo 'Explicit target confirmation received.'
else
    [[ -t 0 ]] || { printf 'ERROR: Interactive confirmation required; expected: %s\n' "$CONFIRMATION_TEXT" >&2; exit 1; }
    read -r -p "Type '${CONFIRMATION_TEXT}' to continue: " CONFIRMATION
    [[ $CONFIRMATION == "$CONFIRMATION_TEXT" ]] || { echo 'Restore cancelled.' >&2; exit 1; }
fi

FORCE_RESTORE="$CONFIRMATION_TEXT" bash "$LOCAL_RESTORE_SCRIPT" "$DUMP_PATH"
echo "SUCCESS: Database restored from s3://${BACKUP_BUCKET}/${DUMP_KEY}"
