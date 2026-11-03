#!/usr/bin/env bash
set -Eeuo pipefail

log() {
    printf '[deploy] %s\n' "$*"
}

if [[ -n "${BASE_URL:-}" ]]; then
    health_url=${BASE_URL%/}
elif [[ ",${COMPOSE_PROFILES:-}," == *,edge,* ]]; then
    health_url=http://localhost
else
    health_url=http://127.0.0.1:5000
fi

health_attempts=${HEALTH_ATTEMPTS:-30}
health_interval=${HEALTH_INTERVAL_SECONDS:-2}
if [[ ! "$health_attempts" =~ ^[1-9][0-9]*$ ]]; then
    log "HEALTH_ATTEMPTS must be a positive integer."
    exit 2
fi

if [[ ! "$health_interval" =~ ^[0-9]+([.][0-9]+)?$ ]]; then
    log "HEALTH_INTERVAL_SECONDS must be a non-negative number."
    exit 2
fi

wait_until_ready() {
    local attempt
    for ((attempt = 1; attempt <= health_attempts; attempt++)); do
        if curl --fail --silent --show-error --location --max-time 5 \
            "${health_url}/health/ready" >/dev/null; then
            return 0
        fi
        if ((attempt < health_attempts)); then
            sleep "$health_interval"
        fi
    done
    return 1
}

previous_container=$(docker compose ps --all --quiet api | head -n 1)
previous_image=
rollback_tag=
if [[ -n "$previous_container" ]]; then
    previous_image=$(docker inspect --format '{{.Image}}' "$previous_container")
    if [[ -n "$previous_image" ]]; then
        rollback_tag="social-network-api:rollback-${BASHPID}-$(date +%s)"
        docker image tag "$previous_image" "$rollback_tag"
    fi
fi

if ! docker compose build api; then
    log "Image build failed; the running stack was left in place."
    exit 1
fi

if docker compose up --detach --no-build; then
    if wait_until_ready; then
        log "Deployment is ready at ${health_url}."
        exit 0
    fi
else
    log "Compose could not start the new stack."
fi

log "Deployment health check failed."
if [[ -n "$previous_image" && -n "$rollback_tag" ]]; then
    if API_IMAGE="$rollback_tag" docker compose up --detach --no-build \
        --force-recreate api; then
        if wait_until_ready; then
            log "Previous API image was restored and passed readiness."
        else
            log "Rollback started, but the previous API did not pass readiness."
        fi
    else
        log "Rollback could not start the previous API image."
    fi
else
    docker compose stop api || true
    log "No previous API image was available for rollback."
fi

# A failed deployment remains a failure even when rollback restored service.
exit 1
