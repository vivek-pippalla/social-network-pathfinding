#!/usr/bin/env bash
# Create one local Neo4j dump and verify the actual uploaded S3 object.
set -Eeuo pipefail
SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
PROJECT_ROOT=$(cd "$SCRIPT_DIR/../../.." && pwd)
LOCAL_BACKUP_SCRIPT=$PROJECT_ROOT/deploy/local/backup.sh
cd "$PROJECT_ROOT"

if [[ -z ${BACKUP_BUCKET:-} && -f .env ]]; then
    BACKUP_BUCKET=$(sed -n 's/^BACKUP_BUCKET=//p' .env | head -n 1 | tr -d '\r' | sed 's/^"//;s/"$//')
fi
[[ -n ${BACKUP_BUCKET:-} && $BACKUP_BUCKET != '<BUCKET_NAME>' ]] || { echo 'ERROR: Set BACKUP_BUCKET to the configured bucket.' >&2; exit 2; }
[[ $BACKUP_BUCKET =~ ^[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]$ ]] || { echo 'ERROR: BACKUP_BUCKET has an invalid bucket-name format.' >&2; exit 2; }
AWS_REGION=${AWS_REGION:-${AWS_DEFAULT_REGION:-}}
if [[ -z $AWS_REGION && -f .env ]]; then AWS_REGION=$(sed -n 's/^AWS_REGION=//p' .env | head -n 1 | tr -d '\r'); fi
[[ -n $AWS_REGION && $AWS_REGION != '<REGION>' ]] || { echo 'ERROR: Set AWS_REGION or AWS_DEFAULT_REGION.' >&2; exit 2; }
command -v aws >/dev/null 2>&1 || { echo 'ERROR: AWS CLI is not installed.' >&2; exit 2; }
for tool in sha256sum python3 cmp; do command -v "$tool" >/dev/null 2>&1 || { printf 'ERROR: Required command not found: %s\n' "$tool" >&2; exit 2; }; done
[[ -f $LOCAL_BACKUP_SCRIPT ]] || { echo 'ERROR: Local backup script is missing.' >&2; exit 2; }

BACKUP_OUTPUT=$(DOCKER_SUDO="${DOCKER_SUDO:-auto}" bash "$LOCAL_BACKUP_SCRIPT" 2>&1) || { printf '%s\n' "$BACKUP_OUTPUT" >&2; echo 'ERROR: Local backup failed.' >&2; exit 1; }
printf '%s\n' "$BACKUP_OUTPUT"
LATEST_DUMP=$(printf '%s\n' "$BACKUP_OUTPUT" | sed -n 's/^BACKUP_PATH=//p' | tail -n 1)
[[ -n $LATEST_DUMP && -f $LATEST_DUMP && -s $LATEST_DUMP ]] || { echo 'ERROR: Backup invocation did not identify a non-empty dump.' >&2; exit 1; }
DUMP_FILENAME=$(basename "$LATEST_DUMP")
[[ $DUMP_FILENAME =~ ^neo4j-([0-9]{8}T[0-9]{6}Z)-[0-9]+\.dump$ ]] || { echo 'ERROR: Backup filename does not contain a valid generated timestamp.' >&2; exit 1; }
TIMESTAMP=${BASH_REMATCH[1]}
SHA256_FILE="$LATEST_DUMP.sha256"
METADATA_FILE="$LATEST_DUMP.metadata.json"
[[ -s $SHA256_FILE && -s $METADATA_FILE ]] || { echo 'ERROR: Backup checksum or Neo4j version metadata is missing.' >&2; exit 1; }
LOCAL_CHECKSUM=$(cut -d ' ' -f 1 "$SHA256_FILE")
[[ $LOCAL_CHECKSUM =~ ^[a-fA-F0-9]{64}$ ]] || { echo 'ERROR: Could not read a valid SHA-256 checksum.' >&2; exit 1; }
[[ $(sha256sum "$LATEST_DUMP" | cut -d ' ' -f 1) == "$LOCAL_CHECKSUM" ]] || { echo 'ERROR: Local dump does not match its checksum sidecar.' >&2; exit 1; }
CHECKSUM_B64=$(LOCAL_SHA256="$LOCAL_CHECKSUM" python3 -c 'import base64, os; print(base64.b64encode(bytes.fromhex(os.environ["LOCAL_SHA256"])).decode())')

REMOTE_DUMP=$(mktemp)
REMOTE_SHA=$(mktemp)
REMOTE_MANIFEST=$(mktemp)
REMOTE_HEAD=$(mktemp)
trap 'rm -f -- "$REMOTE_DUMP" "$REMOTE_SHA" "$REMOTE_MANIFEST" "$REMOTE_HEAD"' EXIT
DEST_PREFIX="s3://${BACKUP_BUCKET}/backups/${TIMESTAMP}"
S3_KEY="backups/${TIMESTAMP}/${DUMP_FILENAME}"
echo "Uploading backup to ${DEST_PREFIX}/"
# Unique timestamp/PID names plus a preflight check prevent routine collisions.
EXISTING_KEYS=$(aws --region "$AWS_REGION" s3api list-objects-v2 --bucket "$BACKUP_BUCKET" \
    --prefix "backups/${TIMESTAMP}/" --query 'Contents[].Key' --output text 2>/dev/null) || {
    echo 'ERROR: Cannot check the destination prefix; check credentials, region, and bucket access.' >&2; exit 1;
}
[[ -z $EXISTING_KEYS || $EXISTING_KEYS == None ]] || { echo 'ERROR: Backup destination prefix already contains objects; refusing to overwrite.' >&2; exit 1; }
aws --region "$AWS_REGION" s3 cp "$LATEST_DUMP" "$DEST_PREFIX/$DUMP_FILENAME" \
    --checksum-algorithm SHA256 --metadata "sha256=$LOCAL_CHECKSUM" --only-show-errors || { echo 'ERROR: S3 dump upload failed; check credentials, region, and bucket access.' >&2; exit 1; }
echo 'Upload completed: dump object transfer succeeded.'
aws --region "$AWS_REGION" s3 cp "$SHA256_FILE" "$DEST_PREFIX/$DUMP_FILENAME.sha256" --only-show-errors || { echo 'ERROR: S3 checksum upload failed; check bucket access.' >&2; exit 1; }
aws --region "$AWS_REGION" s3 cp "$METADATA_FILE" "$DEST_PREFIX/$DUMP_FILENAME.metadata.json" --only-show-errors || { echo 'ERROR: S3 version metadata upload failed; check bucket access.' >&2; exit 1; }

# Never use ETag as a digest: multipart upload and encryption change its meaning.
aws --region "$AWS_REGION" s3api head-object --bucket "$BACKUP_BUCKET" --key "$S3_KEY" \
    --checksum-mode ENABLED > "$REMOTE_HEAD" || { echo 'ERROR: S3 HeadObject failed after upload.' >&2; exit 1; }
readarray -t HEAD_FIELDS < <(python3 - "$REMOTE_HEAD" <<'PY'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as head_file:
    data = json.load(head_file)
print(data.get("ContentLength", ""))
print(data.get("Metadata", {}).get("sha256", ""))
print(data.get("ChecksumSHA256", ""))
print(data.get("ChecksumType", ""))
PY
)
REMOTE_SIZE=${HEAD_FIELDS[0]:-}
REMOTE_METADATA_SHA=${HEAD_FIELDS[1]:-}
REMOTE_S3_CHECKSUM=${HEAD_FIELDS[2]:-}
REMOTE_CHECKSUM_TYPE=${HEAD_FIELDS[3]:-}
LOCAL_SIZE=$(wc -c < "$LATEST_DUMP" | tr -d ' ')
[[ $REMOTE_SIZE == "$LOCAL_SIZE" && $REMOTE_METADATA_SHA == "$LOCAL_CHECKSUM" ]] || { echo 'ERROR: S3 object metadata or content length does not match the local dump.' >&2; exit 1; }
if [[ -n $REMOTE_S3_CHECKSUM && $REMOTE_CHECKSUM_TYPE == FULL_OBJECT && $REMOTE_S3_CHECKSUM != "$CHECKSUM_B64" ]]; then
    echo 'ERROR: S3 full-object SHA-256 checksum differs from local checksum.' >&2; exit 1
fi
echo 'S3 object metadata verified: content length and SHA-256 metadata match.'
if [[ -n $REMOTE_S3_CHECKSUM ]]; then
    echo "S3 returned SHA-256 checksum (type: ${REMOTE_CHECKSUM_TYPE:-unspecified}); composite values are not treated as full-file hashes."
else
    echo 'S3 did not return a SHA-256 checksum; independent content verification will be used.'
fi

aws --region "$AWS_REGION" s3 cp "$DEST_PREFIX/$DUMP_FILENAME" "$REMOTE_DUMP" --only-show-errors || { echo 'ERROR: Cannot download uploaded dump for verification.' >&2; exit 1; }
REMOTE_CHECKSUM=$(sha256sum "$REMOTE_DUMP" | cut -d ' ' -f 1)
[[ -s $REMOTE_DUMP && $REMOTE_CHECKSUM == "$LOCAL_CHECKSUM" ]] || { echo 'ERROR: Independently downloaded S3 object failed SHA-256 verification.' >&2; exit 1; }
aws --region "$AWS_REGION" s3 cp "$DEST_PREFIX/$DUMP_FILENAME.sha256" "$REMOTE_SHA" --only-show-errors || { echo 'ERROR: Cannot download uploaded checksum sidecar.' >&2; exit 1; }
UPLOADED_CHECKSUM=$(cut -d ' ' -f 1 "$REMOTE_SHA")
[[ $UPLOADED_CHECKSUM == "$LOCAL_CHECKSUM" ]] || { echo 'ERROR: Uploaded checksum sidecar does not match local checksum.' >&2; exit 1; }
aws --region "$AWS_REGION" s3 cp "$DEST_PREFIX/$DUMP_FILENAME.metadata.json" "$REMOTE_MANIFEST" --only-show-errors || { echo 'ERROR: Cannot download uploaded version metadata.' >&2; exit 1; }
cmp -s "$METADATA_FILE" "$REMOTE_MANIFEST" || { echo 'ERROR: Uploaded Neo4j version metadata differs from the local manifest.' >&2; exit 1; }
echo 'Content checksum independently verified: downloaded S3 object SHA-256 matches the local dump.'
echo "SUCCESS: Integrity-verified backup at ${DEST_PREFIX}/${DUMP_FILENAME}"
