#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPOSE_FILE="$ROOT_DIR/docker-compose.test.yml"
PROJECT_NAME="social-network-pathfinding-test"

compose() {
  docker compose --project-name "$PROJECT_NAME" --file "$COMPOSE_FILE" "$@"
}

usage() {
  echo "Usage: $0 {up|down|wait}" >&2
  exit 2
}

[[ $# -eq 1 ]] || usage
case "$1" in
  up)
    compose up --detach --wait --wait-timeout 180
    ;;
  down)
    compose down --remove-orphans
    ;;
  wait)
    compose up --detach --wait --wait-timeout 180
    ;;
  *)
    usage
    ;;
esac
