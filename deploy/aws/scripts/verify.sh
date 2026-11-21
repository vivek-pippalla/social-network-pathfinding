#!/usr/bin/env bash
# Post-deployment checks for API availability, privacy, auth, graph, and cache.
set -Eeuo pipefail

BASE_URL=${BASE_URL:-http://localhost}
BASE_URL=${BASE_URL%/}
CONNECT_TIMEOUT=${CONNECT_TIMEOUT:-5}
REQUEST_TIMEOUT=${REQUEST_TIMEOUT:-20}
GRAPH_START_ID=${GRAPH_START_ID:-}
GRAPH_END_ID=${GRAPH_END_ID:-}
TEST_RATE_LIMIT=0
for arg in "$@"; do
    case "$arg" in
        --test-rate-limit) TEST_RATE_LIMIT=1 ;;
        *) printf 'Unknown argument: %s\n' "$arg" >&2; exit 2 ;;
    esac
done
for tool in curl jq python3 mktemp; do
    command -v "$tool" >/dev/null 2>&1 || { printf 'ERROR: Required command not found: %s\n' "$tool" >&2; exit 2; }
done
TMP_DIR=$(mktemp -d) || { echo 'ERROR: Cannot create temporary directory.' >&2; exit 2; }
trap 'rm -rf -- "$TMP_DIR"' EXIT

passed=0
failed=0
pass() { printf '  [PASS] %s\n' "$1"; passed=$((passed + 1)); }
fail() { printf '  [FAIL] %s: %s\n' "$1" "$2" >&2; failed=$((failed + 1)); }
skip() { printf '  [SKIP] %s: %s\n' "$1" "$2"; }

request() {
    local method=$1 url=$2 output=$3 status
    shift 3
    status=$(curl --silent --show-error --connect-timeout "$CONNECT_TIMEOUT" \
        --max-time "$REQUEST_TIMEOUT" --output "$output" --write-out '%{http_code}' \
        --request "$method" "$@" "$url") || status=000
    printf '%s' "$status"
}
json_value() { jq -r "$2" "$1" 2>/dev/null || true; }
jwt_subject() {
    JWT_TOKEN=$1 python3 -c '
import base64, json, os, re, sys
try:
    parts = os.environ["JWT_TOKEN"].split(".")
    if len(parts) != 3 or len(parts[1]) > 8192: raise ValueError
    if not parts[1] or any(c not in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_-" for c in parts[1]): raise ValueError
    payload = parts[1] + "=" * (-len(parts[1]) % 4)
    claims = json.loads(base64.b64decode(payload, altchars=b"-_", validate=True))
    if not isinstance(claims, dict): raise ValueError
    subject = claims.get("sub")
    if not isinstance(subject, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", subject): raise ValueError
    print(subject)
except Exception: sys.exit(1)
'
}

echo "=== Verification Suite: ${BASE_URL} ==="
BODY=$TMP_DIR/health.json
STATUS=$(request GET "$BASE_URL/health" "$BODY")
[[ $STATUS == 200 ]] && pass 'S4: Liveness is healthy' || fail 'S4: Liveness' "Expected 200; received $STATUS"
BODY=$TMP_DIR/ready.json
STATUS=$(request GET "$BASE_URL/health/ready" "$BODY")
[[ $STATUS == 200 ]] && pass 'S5: Readiness is healthy' || fail 'S5: Readiness' "Expected 200; received $STATUS"
if [[ $STATUS == 200 ]] && ! jq -e '.status == "ok" and (.components | type == "object" and length > 0 and all(.[]; . == "ok"))' "$BODY" >/dev/null 2>&1; then
    fail 'S5: Readiness components' 'Response did not report all dependency components as ok'
fi

BODY=$TMP_DIR/metrics.json
STATUS=$(request GET "$BASE_URL/metrics" "$BODY")
[[ $STATUS == 403 || $STATUS == 404 ]] && pass 'S11: Metrics endpoint is not public' || fail 'S11: Metrics isolation' "Expected 403/404; received $STATUS"
for endpoint in docs openapi.json redoc; do
    BODY=$TMP_DIR/$endpoint.json
    STATUS=$(request GET "$BASE_URL/$endpoint" "$BODY")
    [[ $STATUS == 404 ]] && pass "S11: /$endpoint is disabled" || fail "S11: /$endpoint isolation" "Expected 404; received $STATUS"
done

TEST_ID="$(date -u +%Y%m%d%H%M%S)-$$"
TEST_EMAIL="verify-${TEST_ID}@example.test"
TEST_PASS="Verify-${TEST_ID}-Password!"
REGISTER_BODY=$TMP_DIR/register.json
REGISTER_STATUS=$(request POST "$BASE_URL/api/v1/auth/register" "$REGISTER_BODY" \
    -H 'Content-Type: application/json' \
    --data "{\"name\":\"Verification User\",\"email\":\"$TEST_EMAIL\",\"password\":\"$TEST_PASS\"}")
REGISTER_TOKEN=$(json_value "$REGISTER_BODY" '.access_token // empty')
USER_ID=
REGISTRATION_VALID=0
if [[ $REGISTER_STATUS == 201 && -n $REGISTER_TOKEN ]]; then
    if USER_ID=$(jwt_subject "$REGISTER_TOKEN"); then REGISTRATION_VALID=1; pass 'F2: Registration issued a token with a subject';
    else fail 'F2: Registration token' 'JWT subject could not be decoded'; fi
else fail 'F2: Registration' "Expected 201 and access token; received $REGISTER_STATUS"; fi

LOGIN_BODY=$TMP_DIR/login.json
LOGIN_STATUS=$(request POST "$BASE_URL/api/v1/auth/token" "$LOGIN_BODY" \
    -H 'Content-Type: application/x-www-form-urlencoded' \
    --data-urlencode "username=$TEST_EMAIL" --data-urlencode "password=$TEST_PASS")
LOGIN_TOKEN=$(json_value "$LOGIN_BODY" '.access_token // empty')
TOKEN_TYPE=$(json_value "$LOGIN_BODY" '.token_type // empty')
if [[ $LOGIN_STATUS == 200 && -n $LOGIN_TOKEN && $TOKEN_TYPE == bearer ]]; then
    pass 'F2: Login issued a bearer token'
    BODY=$TMP_DIR/login-profile.json
    STATUS=$(request GET "$BASE_URL/api/v1/users/me" "$BODY" -H "Authorization: Bearer $LOGIN_TOKEN")
    [[ $STATUS == 200 && $(json_value "$BODY" '.email // empty') == "$TEST_EMAIL" ]] && pass 'F2: Login token authorizes own-profile access' || fail 'F2: Login token authorization' "Expected own profile with HTTP 200; received $STATUS"
else fail 'F2: Login' "Expected HTTP 200 and bearer token; received $LOGIN_STATUS"; fi

if [[ $REGISTRATION_VALID == 1 ]]; then
    BODY=$TMP_DIR/profile.json
    STATUS=$(request GET "$BASE_URL/api/v1/users/me" "$BODY" -H "Authorization: Bearer $REGISTER_TOKEN")
    [[ $STATUS == 200 && $(json_value "$BODY" '.email // empty') == "$TEST_EMAIL" ]] && pass 'F2: Own profile returns account email' || fail 'F2: Own profile' "Expected matching email; received HTTP $STATUS"
    BODY=$TMP_DIR/public-profile.json
    STATUS=$(request GET "$BASE_URL/api/v1/users/$USER_ID" "$BODY" -H "Authorization: Bearer $REGISTER_TOKEN")
    if [[ $STATUS == 200 ]] && jq -e 'has("email") == false and has("password_hash") == false' "$BODY" >/dev/null 2>&1; then
        pass 'F3: Public profile omits email and password hash'
    else fail 'F3: Public profile privacy' "Expected 200 without private fields; received HTTP $STATUS"; fi
    BODY=$TMP_DIR/unauth-public-profile.json
    STATUS=$(request GET "$BASE_URL/api/v1/users/$USER_ID" "$BODY")
    [[ $STATUS == 401 && $(json_value "$BODY" '.error.code // empty') == UNAUTHENTICATED ]] && pass 'F3: Public profile route still requires authentication' || fail 'F3: Public profile authorization' "Expected 401 UNAUTHENTICATED; received $STATUS"
else skip 'F2/F3: Profile checks' 'Registration did not provide a usable identity'; fi

BODY=$TMP_DIR/unauth.json
STATUS=$(request GET "$BASE_URL/api/v1/users/me" "$BODY")
[[ $STATUS == 401 && $(json_value "$BODY" '.error.code // empty') == UNAUTHENTICATED ]] && pass 'F2: Unauthenticated profile request is rejected' || fail 'F2: Authentication boundary' "Expected 401 UNAUTHENTICATED; received $STATUS"

if [[ -n $REGISTER_TOKEN ]]; then
    if [[ -z $GRAPH_START_ID || -z $GRAPH_END_ID ]]; then
        skip 'F6/F8: Path and cache' 'Set GRAPH_START_ID and GRAPH_END_ID to known connected dataset nodes'
    else
        AUTH_HEADER="Authorization: Bearer $REGISTER_TOKEN"
        PATH_URL="$BASE_URL/api/v1/path/$GRAPH_START_ID/$GRAPH_END_ID"
        BODY=$TMP_DIR/path-first.json
        STATUS=$(request GET "$PATH_URL" "$BODY" -H "$AUTH_HEADER")
        CACHE_VALUE=$(json_value "$BODY" '.cached | if type == "boolean" then tostring else "invalid" end')
        if [[ $STATUS == 200 ]] && jq -e '.hops | type == "integer" and . >= 0' "$BODY" >/dev/null 2>&1 && [[ $CACHE_VALUE == true || $CACHE_VALUE == false ]]; then
            pass 'F6: Path response has a valid hop count and Boolean cache field'
        else fail 'F6: Path response' "Expected HTTP 200, integer hops and Boolean cached; received $STATUS"; fi
        BODY=$TMP_DIR/path-repeat.json
        STATUS=$(request GET "$PATH_URL" "$BODY" -H "$AUTH_HEADER")
        WARM_CACHED=$(json_value "$BODY" '.cached | if type == "boolean" then tostring else "invalid" end')
        [[ $STATUS == 200 && $WARM_CACHED == true ]] && pass 'F8: Repeated path request is cached' || fail 'F8: Warm cache' "Expected HTTP 200 and cached=true; received $STATUS"
    fi
    BODY=$TMP_DIR/suggestions.json
    STATUS=$(request GET "$BASE_URL/api/v1/suggestions/me" "$BODY" -H "Authorization: Bearer $REGISTER_TOKEN")
    if [[ $STATUS == 200 ]] && jq -e '.items | type == "array"' "$BODY" >/dev/null 2>&1; then pass 'F7: Suggestions returns an items array';
    else fail 'F7: Suggestions' "Expected HTTP 200 with items array; received $STATUS"; fi
else skip 'F6/F7/F8: Graph checks' 'Registration did not provide a usable token'; fi

if [[ $TEST_RATE_LIMIT == 1 ]]; then
    limited=0
    for _ in 1 2 3 4 5 6; do
        BODY=$TMP_DIR/rate-limit.json
        RATE_STATUS=$(request POST "$BASE_URL/api/v1/auth/token" "$BODY" \
            -H 'Content-Type: application/x-www-form-urlencoded' \
            --data-urlencode 'username=rate-limit-test@example.test' --data-urlencode 'password=invalid-password')
        if [[ $RATE_STATUS == 429 ]]; then limited=1; break; fi
        [[ $RATE_STATUS == 000 ]] && break
    done
    if [[ $limited == 1 ]]; then pass 'F10: Rate limit returned HTTP 429';
    else fail 'F10: Rate limit' "HTTP 429 not observed; last status $RATE_STATUS"; fi
fi

printf 'Verification complete: %s passed, %s failed\n' "$passed" "$failed"
(( failed == 0 ))
