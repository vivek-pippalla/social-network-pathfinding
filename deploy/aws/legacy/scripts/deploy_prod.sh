#!/usr/bin/env bash
# ==============================================================================
# deploy_prod.sh — Pull from ECR, Run Production Stack on EC2 & Auto-Rollback
# ==============================================================================
set -euo pipefail

APP_DIR="/opt/social-network-pathfinding"
cd "$APP_DIR"

if [ ! -f .env.prod ]; then
    echo "ERROR: Missing .env.prod file in $APP_DIR."
    echo "Create .env.prod with required production variables before running."
    exit 1
fi

# Load environment variables
set -a
source .env.prod
set +a

AWS_REGION="${AWS_REGION:-ap-south-1}"
ECR_REGISTRY="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"
CONTAINER_NAME="social-network-api-prod"

check_api_health() {
    # Verify API container internally (port 5000 is internal to Docker network)
    docker exec "$CONTAINER_NAME" curl -s -f http://localhost:5000/health >/dev/null 2>&1
}

echo "=== Deploying Social Network Pathfinding Stack ==="

# Step 0: Record currently running image ID for safe rollback
PREV_IMAGE_ID=$(docker inspect --format='{{.Image}}' "$CONTAINER_NAME" 2>/dev/null || echo "")
if [ -n "$PREV_IMAGE_ID" ]; then
    echo "Current running image ID: $PREV_IMAGE_ID (saved for rollback)"
else
    echo "No prior container running; this is an initial deployment."
fi

echo "Step 1: Authenticating Docker with AWS ECR..."
aws ecr get-login-password --region "${AWS_REGION}" | docker login --username AWS --password-stdin "${ECR_REGISTRY}"

echo "Step 2: Pulling latest application image..."
docker compose -f docker-compose.prod.yml pull api

echo "Step 3: Starting / Upgrading production containers..."
docker compose -f docker-compose.prod.yml up -d --remove-orphans

echo "Step 4: Verifying API healthcheck..."
ATTEMPTS=0
MAX_ATTEMPTS=24

until check_api_health; do
    ATTEMPTS=$((ATTEMPTS + 1))
    if [ "$ATTEMPTS" -ge "$MAX_ATTEMPTS" ]; then
        echo "ERROR: Health check timed out after $((MAX_ATTEMPTS * 5)) seconds on $CONTAINER_NAME."
        echo "=== Container Failure Logs ==="
        docker compose -f docker-compose.prod.yml logs --tail=50 api

        if [ -n "$PREV_IMAGE_ID" ]; then
            echo "Initiating automatic rollback to previous stable image: $PREV_IMAGE_ID..."
            
            # Tag previous image ID locally as rollback-target
            docker tag "$PREV_IMAGE_ID" "${ECR_REGISTRY}/social-network-api:rollback-target"
            
            # Force recreate API container with local rollback image without pulling
            IMAGE_TAG="rollback-target" docker compose -f docker-compose.prod.yml up -d --pull never api
            
            # Bounded verification of the rolled-back container
            echo "Verifying health of restored container..."
            ROLLBACK_ATTEMPTS=0
            ROLLBACK_MAX=10
            until check_api_health; do
                ROLLBACK_ATTEMPTS=$((ROLLBACK_ATTEMPTS + 1))
                if [ "$ROLLBACK_ATTEMPTS" -ge "$ROLLBACK_MAX" ]; then
                    break
                fi
                sleep 5
            done

            if check_api_health; do
                echo "Rollback SUCCESS: Previous stable container restored and confirmed healthy."
            else
                echo "Rollback CRITICAL FAILURE: Restored container failed health check."
                docker compose -f docker-compose.prod.yml logs --tail=50 api
            fi
        else
            echo "Rollback not possible: No prior container image was running on this host."
        fi
        exit 1
    fi
    echo "Waiting for healthy status... ($ATTEMPTS/$MAX_ATTEMPTS)"
    sleep 5
done

echo "Step 5: Verifying Caddy reverse proxy..."
docker compose -f docker-compose.prod.yml ps caddy

echo "=== Deployment Successful & Verified! ==="
docker compose -f docker-compose.prod.yml ps
echo "API Internal Health Check:"
docker exec "$CONTAINER_NAME" curl -s http://localhost:5000/health | jq . 2>/dev/null || docker exec "$CONTAINER_NAME" curl -s http://localhost:5000/health
if [ -n "${DOMAIN_NAME:-}" ] && [ "$DOMAIN_NAME" != "localhost" ]; then
    echo "Public HTTPS Endpoint: https://${DOMAIN_NAME}"
fi
