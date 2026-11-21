#!/usr/bin/env bash
# ==============================================================================
# deploy/aws/scripts/verify.sh — Post-deployment smoke and functional verification
# Safe to run locally on EC2 or remotely against BASE_URL.
# ==============================================================================
set -Eeuo pipefail

BASE_URL="${BASE_URL:-http://localhost}"
BASE_URL="${BASE_URL%/}"
TEST_RATE_LIMIT=0
CONNECT_TIMEOUT="${CONNECT_TIMEOUT_SECONDS:-5}"
REQUEST_TIMEOUT="${REQUEST_TIMEOUT_SECONDS:-20}"

for arg in "$@"; do
    case "$arg" in
        --test-rate-limit) TEST_RATE_LIMIT=1 ;;
        -h|--help)
            cat <<'USAGE'
Usage: verify.sh [--test-rate-limit]

Environment:
  BASE_URL                    Base URL (default: http://localhost)
  CONNECT_TIMEOUT_SECONDS     Curl connection timeout (default: 5)
  REQUEST_TIMEOUT_SECONDS     Curl total request timeout (default: 20)

The script creates a disposable test account. Rate-limit testing is optional
because it deliberately consumes login attempts for one client IP.
USAGE
            exit 0
            ;;
        *)
            echo "ERROR: Unknown argument: $arg" >&2
            exit 2
            ;;
    esac
done

for tool in curl jq date; do
    if ! command -v "$tool" >/dev/null 2>&1; then
        echo "ERROR: Required command not found: $tool" >&2
        exit 2
    fi
done

for value in "$CONNECT_TIMEOUT" "$REQUEST_TIMEOUT"; do
    if [[ ! "$value" =~ ^[1-9][0-9]*([.][0-9]+)?$ ]]; then
        echo "ERROR: Timeout values must be positive numbers." >&2
        exit 2
    fi
done

PASSED_COUNT=0
FAILED_COUNT=0
ACCESS_TOKEN=""
USER_ID=""
TEST_EMAIL=""
TEST_PASS=""

pass() {
    printf '  [PASS] %s\n' "$1"
    PASSED_COUNT=$((PASSED_COUNT + 1))
}

fail() {
    printf '  [FAIL] %s: %s\n' "$1" "$2" >&2
    FAILED_COUNT=$((FAILED_COUNT + 1))
}

request_status() {
    local method="$1"
    local url="$2"
    shift 2
    curl --silent --show-error --output /dev/null --write-out '%{http_code}' \
        --connect-timeout "$CONNECT_TIMEOUT" --max-time "$REQUEST_TIMEOUT" \
        --request "$method" "$@" "$url"
}

request_body() {
    local method="$1"
    local url="$2"
    shift 2
    curl --silent --show-error --connect-timeout "$CONNECT_TIMEOUT" \
        --max-time "$REQUEST_TIMEOUT" --request "$method" "$@" "$url"
}

json_value() {
    local body="$1"
    local expression="$2"
    jq -r "$expression" <<<"$body" 2>/dev/null || true
}

echo "=== Running verification suite against ${BASE_URL} ==="

# 1. Liveness and readiness
if STATUS=$(request_status GET "${BASE_URL}/health" 2>/dev/null) && [[ "$STATUS" == "200" ]]; then
    pass "S4: Liveness probe returns HTTP 200"
else
    fail "S4: Liveness probe" "${STATUS:-request failed}"
fi

READY_BODY=""
if READY_BODY=$(request_body GET "${BASE_URL}/health/ready" 2>/dev/null) &&
    READY_STATUS=$(request_status GET "${BASE_URL}/health/ready" 2>/dev/null) &&
    [[ "$READY_STATUS" == "200" ]]; then
    pass "S5: Readiness probe returns HTTP 200"
else
    fail "S5: Readiness probe" "Expected HTTP 200; status ${READY_STATUS:-request failed}"
fi

# 2. Production-only endpoints
if METRICS_STATUS=$(request_status GET "${BASE_URL}/metrics" 2>/dev/null) &&
    [[ "$METRICS_STATUS" == "404" || "$METRICS_STATUS" == "403" ]]; then
    pass "S11: Public /metrics endpoint is blocked (${METRICS_STATUS})"
else
    fail "S11: Public /metrics endpoint" "Expected 403/404; got ${METRICS_STATUS:-request failed}"
fi

if DOCS_STATUS=$(request_status GET "${BASE_URL}/docs" 2>/dev/null) &&
    [[ "$DOCS_STATUS" == "404" ]]; then
    pass "S11: Swagger /docs is disabled"
else
    fail "S11: Swagger /docs endpoint" "Expected 404; got ${DOCS_STATUS:-request failed}"
fi

# 3. Register a unique disposable account. Skip dependent checks if this fails.
TEST_ID="$(date -u +%Y%m%d%H%M%S)-$RANDOM"
TEST_EMAIL="verify-${TEST_ID}@example.test"
TEST_NAME="Deployment Verification"
TEST_PASS="Verify-${TEST_ID}-Aa9!"

REGISTER_BODY=""
if REGISTER_BODY=$(request_body POST "${BASE_URL}/api/v1/auth/register" \
    --header 'Content-Type: application/json' \
    --data "$(jq -cn --arg name "$TEST_NAME" --arg email "$TEST_EMAIL" --arg password "$TEST_PASS" \
        '{name:$name,email:$email,password:$password}')"); then
    USER_ID="$(json_value "$REGISTER_BODY" '.id // empty')"
fi

if [[ -n "$USER_ID" && "$USER_ID" != "null" ]]; then
    pass "F2: Disposable test account registered"
else
    fail "F2: User registration" "Registration did not return a user id"
fi

# 4. Token issuance and authenticated checks
TOKEN_BODY=""
if [[ -n "$USER_ID" ]] &&
    TOKEN_BODY=$(request_body POST "${BASE_URL}/api/v1/auth/token" \
        --header 'Content-Type: application/x-www-form-urlencoded' \
        --data-urlencode "username=$TEST_EMAIL" \
        --data-urlencode "password=$TEST_PASS"); then
    ACCESS_TOKEN="$(json_value "$TOKEN_BODY" '.access_token // empty')"
fi

if [[ -n "$ACCESS_TOKEN" && "$ACCESS_TOKEN" != "null" ]]; then
    pass "F2: Token issuance successful"
else
    fail "F2: Token issuance" "No access token was returned"
fi

if [[ -n "$ACCESS_TOKEN" ]]; then
    PROFILE_BODY=""
    if PROFILE_BODY=$(request_body GET "${BASE_URL}/api/v1/users/me" \
        --header "Authorization: Bearer $ACCESS_TOKEN") &&
        [[ "$(json_value "$PROFILE_BODY" '.email // empty')" == "$TEST_EMAIL" ]]; then
        pass "F2: Authenticated profile returns the caller's private email"
    else
        fail "F2: Authenticated profile" "Profile did not match the disposable test account"
    fi

    UNAUTH_BODY=""
    if UNAUTH_BODY=$(request_body GET "${BASE_URL}/api/v1/users/me" 2>/dev/null) &&
        UNAUTH_STATUS=$(request_status GET "${BASE_URL}/api/v1/users/me" 2>/dev/null) &&
        [[ "$UNAUTH_STATUS" == "401" ]] &&
        [[ "$(json_value "$UNAUTH_BODY" '.error.code // empty')" == "UNAUTHENTICATED" ]]; then
        pass "F2: Protected profile rejects unauthenticated requests"
    else
        fail "F2: Unauthenticated protection" "Expected HTTP 401 and UNAUTHENTICATED envelope"
    fi

    PUBLIC_BODY=""
    if PUBLIC_BODY=$(request_body GET "${BASE_URL}/api/v1/users/$USER_ID" 2>/dev/null) &&
        [[ -z "$(json_value "$PUBLIC_BODY" '.email // empty')" ]] &&
        [[ -z "$(json_value "$PUBLIC_BODY" '.password_hash // empty')" ]]; then
        pass "F3: Public profile does not expose credentials"
    else
        fail "F3: Public profile privacy" "Public profile contained a private field or request failed"
    fi

    # Cache behavior must be valid for both a cold and a warm cache. Do not
    # assume the instance has an empty cache when this verifier is re-run.
    PATH_URL="${BASE_URL}/api/v1/path/0/107"
    COLD_BODY=""
    if COLD_BODY=$(request_body GET "$PATH_URL" \
        --header "Authorization: Bearer $ACCESS_TOKEN") &&
        [[ "$(json_value "$COLD_BODY" '.hops // -1')" == "1" ]] &&
        [[ "$(json_value "$COLD_BODY" '.cached // empty')" =~ ^(true|false)$ ]]; then
        FIRST_CACHED="$(json_value "$COLD_BODY" '.cached')"
        pass "F6: Shortest path 0 -> 107 returns one hop (cached: $FIRST_CACHED)"
    else
        fail "F6: Shortest path" "Expected a one-hop path response"
    fi

    WARM_BODY=""
    if WARM_BODY=$(request_body GET "$PATH_URL" \
        --header "Authorization: Bearer $ACCESS_TOKEN") &&
        [[ "$(json_value "$WARM_BODY" '.hops // -1')" == "1" ]] &&
        [[ "$(json_value "$WARM_BODY" '.cached // empty')" == "true" ]]; then
        pass "F8: Repeated shortest path query hits Redis cache"
    else
        fail "F8: Redis cache" "Repeated valid path query did not report cached=true"
    fi

    SUGGESTIONS_STATUS=""
    if SUGGESTIONS_STATUS=$(request_status GET "${BASE_URL}/api/v1/suggestions/me" \
        --header "Authorization: Bearer $ACCESS_TOKEN" 2>/dev/null) &&
        [[ "$SUGGESTIONS_STATUS" == "200" ]]; then
        pass "F7: Friend recommendations endpoint returns HTTP 200"
    else
        fail "F7: Friend recommendations" "Expected HTTP 200; got ${SUGGESTIONS_STATUS:-request failed}"
    fi
else
    fail "F2-F8: Authenticated verification" "Skipped because token issuance failed"
fi

# 5. Optional rate-limit test; intentionally consumes login attempts.
if [[ "$TEST_RATE_LIMIT" == "1" ]]; then
    echo "--- Testing rate limiter (up to 6 login attempts) ---"
    LIMITED=0
    RL_STATUS=""
    for _ in $(seq 1 6); do
        if RL_STATUS=$(request_status POST "${BASE_URL}/api/v1/auth/token" \
            --header 'Content-Type: application/x-www-form-urlencoded' \
            --data-urlencode 'username=verify-rate-limit@example.test' \
            --data-urlencode 'password=not-a-real-password' 2>/dev/null); then
            if [[ "$RL_STATUS" == "429" ]]; then
                LIMITED=1
                break
            fi
        fi
    done
    if [[ "$LIMITED" == "1" ]]; then
        pass "F10: Login rate limiter returned HTTP 429"
    else
        fail "F10: Login rate limiter" "Expected HTTP 429; last status ${RL_STATUS:-request failed}"
    fi
fi

echo "=========================================================="
printf ' Verification complete: %s passed, %s failed\n' "$PASSED_COUNT" "$FAILED_COUNT"
echo "=========================================================="

if ((FAILED_COUNT > 0)); then
    exit 1
fi
