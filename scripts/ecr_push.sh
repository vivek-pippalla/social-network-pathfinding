#!/usr/bin/env bash
# ==============================================================================
# ecr_push.sh — Build and push social-network-api Docker image to AWS ECR
# ==============================================================================
set -euo pipefail

AWS_REGION="${AWS_REGION:-ap-south-1}"
AWS_ACCOUNT_ID="${AWS_ACCOUNT_ID:-}"
IMAGE_REPO="social-network-api"
IMAGE_TAG="${IMAGE_TAG:-$(git rev-parse --short HEAD 2>/dev/null || echo 'latest')}"

if [ -z "$AWS_ACCOUNT_ID" ]; then
    echo "ERROR: AWS_ACCOUNT_ID environment variable is required."
    echo "Usage: AWS_ACCOUNT_ID=123456789012 AWS_REGION=ap-south-1 ./scripts/ecr_push.sh"
    exit 1
fi

ECR_REGISTRY="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"
FULL_IMAGE_URI="${ECR_REGISTRY}/${IMAGE_REPO}:${IMAGE_TAG}"
LATEST_IMAGE_URI="${ECR_REGISTRY}/${IMAGE_REPO}:latest"

echo "=== AWS ECR Build & Push Pipeline ==="
echo "Registry: ${ECR_REGISTRY}"
echo "Repository: ${IMAGE_REPO}"
echo "Tag: ${IMAGE_TAG}"
echo "Region: ${AWS_REGION}"

echo "Step 1: Authenticating Docker with ECR..."
aws ecr get-login-password --region "${AWS_REGION}" | docker login --username AWS --password-stdin "${ECR_REGISTRY}"

echo "Step 2: Building Docker image..."
docker build -t "${IMAGE_REPO}:${IMAGE_TAG}" .

echo "Step 3: Tagging images..."
docker tag "${IMAGE_REPO}:${IMAGE_TAG}" "${FULL_IMAGE_URI}"
docker tag "${IMAGE_REPO}:${IMAGE_TAG}" "${LATEST_IMAGE_URI}"

echo "Step 4: Pushing images to ECR..."
docker push "${FULL_IMAGE_URI}"
docker push "${LATEST_IMAGE_URI}"

echo "=== Successfully pushed to ECR: ${FULL_IMAGE_URI} ==="
