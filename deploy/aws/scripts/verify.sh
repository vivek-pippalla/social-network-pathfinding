#!/usr/bin/env bash
# ==============================================================================
# deploy/aws/scripts/verify.sh — Post-Deployment Verification Suite
# Verifies health, security boundaries, authentication, graph pathfinding, and caching.
# ==============================================================================
set -euo pipefail

BASE_URL="${BASE_URL:-http://localhost}"
BASE_URL="${BASE_URL%/}"
TEST_RATE_LIMIT=0

for arg in "$@"; do
    if [ "$arg" = "--test-rate-limit" ]; then
        TEST_RATE_LIMIT=1
    fi
done

PASSED_COUNT=0
FAILED_COUNT=0

pass() {
    echo "  [PASS] $1"
    PASSED_COUNT=$((PASSED_COUNT + 1))
}

fail() {
    echo "  [FAIL] $1: $2" >&2
    FAILED_COUNT=$((FAILED_COUNT + 1))
}

echo "=== Running Verification Suite against ${BASE_URL} ==="

# 1. S4: Health Liveness Probe
STATUS=$(curl -s -o /dev/null -w "%{http_code}" "${BASE_URL}/health" || echo "000")
if [ "${STATUS}" = "200" ]; then
    pass "S4: Liveness probe returns 200 OK"
else
    fail "S4: Liveness probe failed" "Expected 200, got ${STATUS}"
fi

# 2. S5: Health Readiness Probe (Deep Check: Neo4j + Redis)
READY_BODY=$(curl -s "${BASE_URL}/health/ready" || echo "{}")
READY_STATUS=$(curl -s -o /dev/null -w "%{http_code}" "${BASE_URL}/health/ready" || echo "000")
if [ "${READY_STATUS}" = "200" ]; then
    pass "S5: Readiness probe returns 200 OK (all dependencies healthy)"
else
    fail "S5: Readiness probe failed" "Status: ${READY_STATUS}, Body: ${READY_BODY}"
fi

# 3. S11: Operational Endpoint Isolation (/metrics blocked, /docs off)
METRICS_STATUS=$(curl -s -o /dev/null -w "%{http_code}" "${BASE_URL}/metrics" || echo "000")
DOCS_STATUS=$(curl -s -o /dev/null -w "%{http_code}" "${BASE_URL}/docs" || echo "000")

if [ "${METRICS_STATUS}" = "404" ] || [ "${METRICS_STATUS}" = "403" ]; then
    pass "S11: Prometheus /metrics endpoint is blocked from public access (${METRICS_STATUS})"
else
    fail "S11: Public exposure of /metrics" "Expected 404/403, got ${METRICS_STATUS}"
fi

if [ "${DOCS_STATUS}" = "404" ]; then
    pass "S11: Swagger /docs is disabled in production (${DOCS_STATUS})"
else
    fail "S11: Public exposure of /docs" "Expected 404, got ${DOCS_STATUS}"
fi

# 4. F2: Authentication Journey (Register, Token Issuance, Protected Route)
TEST_ID=$(date +%s%N | cut -b1-12)
TEST_EMAIL="verify-${TEST_ID}@example.test"
TEST_NAME="Verification User"
TEST_PASS="VerificationPassword123!"

REGISTER_RESP=$(curl -s -X POST "${BASE_URL}/api/v1/auth/register" \
    -H "Content-Type: application/json" \
    -d "{\"name\": \"${TEST_NAME}\", \"email\": \"${TEST_EMAIL}\", \"password\": \"${TEST_PASS}\"}")

USER_ID=$(echo "${REGISTER_RESP}" | jq -r '.id // empty')
if [ -n "${USER_ID}" ] && [ "${USER_ID}" != "null" ]; then
    pass "F2: User registration successful (Account created: ${USER_ID})"
else
    fail "F2: User registration failed" "${REGISTER_RESP}"
fi

TOKEN_RESP=$(curl -s -X POST "${BASE_URL}/api/v1/auth/token" \
    -H "Content-Type: application/x-www-form-urlencoded" \
    -d "username=${TEST_EMAIL}&password=${TEST_PASS}")

ACCESS_TOKEN=$(echo "${TOKEN_RESP}" | jq -r '.access_token // empty')
if [ -n "${ACCESS_TOKEN}" ] && [ "${ACCESS_TOKEN}" != "null" ]; then
    pass "F2: Token issuance successful (JWT issued)"
else
    fail "F2: Token acquisition failed" "${TOKEN_RESP}"
fi

# Protected profile with valid token
PROFILE_RESP=$(curl -s "${BASE_URL}/api/v1/users/me" \
    -H "Authorization: Bearer ${ACCESS_TOKEN}")
PROFILE_EMAIL=$(echo "${PROFILE_RESP}" | jq -r '.email // empty')

if [ "${PROFILE_EMAIL}" = "${TEST_EMAIL}" ]; then
    pass "F2: Authenticated /users/me returns caller's private email"
else
    fail "F2: Authenticated /users/me failed" "${PROFILE_RESP}"
fi

# Unauthenticated call to protected route must return 401 with standard error envelope
UNAUTH_STATUS=$(curl -s -o /dev/null -w "%{http_code}" "${BASE_URL}/api/v1/users/me")
UNAUTH_BODY=$(curl -s "${BASE_URL}/api/v1/users/me")
ERROR_CODE=$(echo "${UNAUTH_BODY}" | jq -r '.error.code // empty')

if [ "${UNAUTH_STATUS}" = "401" ] && [ "${ERROR_CODE}" = "UNAUTHENTICATED" ]; then
    pass "F2: Unauthenticated request returns 401 with standard error envelope"
else
    fail "F2: Unauthenticated protection failure" "Status: ${UNAUTH_STATUS}, Code: ${ERROR_CODE}"
fi

# 5. F3: Public Profile Privacy (email and password hash must never be visible)
PUBLIC_RESP=$(curl -s "${BASE_URL}/api/v1/users/${USER_ID}")
PUBLIC_EMAIL=$(echo "${PUBLIC_RESP}" | jq -r '.email // empty')
PUBLIC_PASS=$(echo "${PUBLIC_RESP}" | jq -r '.password_hash // empty')

if [ -z "${PUBLIC_EMAIL}" ] && [ -z "${PUBLIC_PASS}" ]; then
    pass "F3: Public profile strictly isolates credentials (no email or password_hash)"
else
    fail "F3: Credential leak in public profile" "${PUBLIC_RESP}"
fi

# 6. F6 & F8: Shortest Path Calculation and Redis Caching
if [ -n "${ACCESS_TOKEN}" ]; then
    PATH_URL="${BASE_URL}/api/v1/path/0/107"
    COLD_RESP=$(curl -s "${PATH_URL}" -H "Authorization: Bearer ${ACCESS_TOKEN}")
    COLD_HOPS=$(echo "${COLD_RESP}" | jq -r '.hops // -1')
    COLD_CACHED=$(echo "${COLD_RESP}" | jq -r '.cached // empty')

    if [ "${COLD_HOPS}" = "1" ] && [ "${COLD_CACHED}" = "false" ]; then
        pass "F6: Cold shortest path query (0 -> 107) returns 1 hop (cached: false)"
    else
        fail "F6: Cold shortest path calculation failed" "${COLD_RESP}"
    fi

    WARM_RESP=$(curl -s "${PATH_URL}" -H "Authorization: Bearer ${ACCESS_TOKEN}")
    WARM_CACHED=$(echo "${WARM_RESP}" | jq -r '.cached // empty')

    if [ "${WARM_CACHED}" = "true" ]; then
        pass "F8: Repeated shortest path query hits Redis cache (cached: true)"
    else
        fail "F8: Redis cache hit verification failed" "${WARM_RESP}"
    fi

    # 7. F7: Friend Recommendations / Suggestions
    SUGG_RESP=$(curl -s "${BASE_URL}/api/v1/suggestions/me" -H "Authorization: Bearer ${ACCESS_TOKEN}")
    SUGG_STATUS=$(curl -s -o /dev/null -w "%{http_code}" "${BASE_URL}/api/v1/suggestions/me" -H "Authorization: Bearer ${ACCESS_TOKEN}")

    if [ "${SUGG_STATUS}" = "200" ]; then
        pass "F7: Friend recommendations endpoint returns 200 OK"
    else
        fail "F7: Recommendations query failed" "Status: ${SUGG_STATUS}"
    fi
fi

# 8. Optional F10: Rate Limiting Verification
if [ "${TEST_RATE_LIMIT}" = "1" ]; then
    echo "--- Testing Rate Limiter (6 rapid login attempts) ---"
    LIMITED=0
    for i in $(seq 1 6); do
        RL_STATUS=$(curl -s -o /dev/null -w "%{http_code}" -X POST "${BASE_URL}/api/v1/auth/token" \
            -H "Content-Type: application/x-www-form-urlencoded" \
            -d "username=fake@example.test&password=badpassword" || echo "000")
        if [ "${RL_STATUS}" = "429" ]; then
            LIMITED=1
            break
        fi
    done
    if [ "${LIMITED}" = "1" ]; then
        pass "F10: Rate limiting triggered successfully (HTTP 429 RATE_LIMITED)"
    else
        fail "F10: Rate limiter did not engage on 6th attempt" "Status: ${RL_STATUS}"
    fi
fi

echo "=========================================================="
echo " Verification Complete: ${PASSED_COUNT} passed, ${FAILED_COUNT} failed"
echo "=========================================================="

if [ "${FAILED_COUNT}" -gt 0 ]; then
    exit 1
fi
exit 0
