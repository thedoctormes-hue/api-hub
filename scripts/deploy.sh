#!/usr/bin/env bash
#
# Deploy script for api-hub
# Usage: ./scripts/deploy.sh [--no-build] [--branch <branch>]
#
# Steps:
#   1. git pull (or checkout branch)
#   2. docker-compose build
#   3. docker-compose up -d
#   4. health check
#   5. rollback on failure

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR"

# Config
HEALTH_URL="http://localhost:8000/health"
HEALTH_RETRIES=10
HEALTH_INTERVAL=3
COMPOSE_FILE="docker-compose.yml"
BACKUP_TAG="api-hub:previous"

# Parse args
BRANCH=""
NO_BUILD=false

while [[ $# -gt 0 ]]; do
    case "$1" in
        --branch)
            BRANCH="$2"
            shift 2
            ;;
        --no-build)
            NO_BUILD=true
            shift
            ;;
        *)
            echo "Unknown arg: $1"
            exit 1
            ;;
    esac
done

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"
}

error() {
    log "ERROR: $*" >&2
}

rollback() {
    error "Deploy failed. Rolling back..."
    docker tag "$BACKUP_TAG" api-hub:latest 2>/dev/null || true
    docker-compose -f "$COMPOSE_FILE" down 2>/dev/null || true
    docker-compose -f "$COMPOSE_FILE" up -d 2>/dev/null || true
    log "Rollback complete."
}

# Trap errors
trap 'rollback' ERR

log "=== Starting deploy ==="

# Step 1: Git pull
if [[ -n "$BRANCH" ]]; then
    log "Checking out branch: $BRANCH"
    git fetch origin "$BRANCH"
    git checkout "$BRANCH"
fi

log "Pulling latest changes..."
git pull --ff-only

# Step 2: Backup current image
if docker inspect api-hub:latest &>/dev/null; then
    log "Tagging current image as previous..."
    docker tag api-hub:latest "$BACKUP_TAG" 2>/dev/null || true
fi

# Step 3: Build
if [[ "$NO_BUILD" == "false" ]]; then
    log "Building Docker image..."
    docker-compose -f "$COMPOSE_FILE" build --no-cache
else
    log "Skipping build (--no-build)"
fi

# Step 4: Deploy
log "Starting containers..."
docker-compose -f "$COMPOSE_FILE" up -d

# Step 5: Health check
log "Waiting for service to start..."
for i in $(seq 1 "$HEALTH_RETRIES"); do
    sleep "$HEALTH_INTERVAL"

    if curl -sf "$HEALTH_URL" > /dev/null 2>&1; then
        log "Health check passed (attempt $i/$HEALTH_RETRIES)"

        # Verify response
        RESPONSE=$(curl -sf "$HEALTH_URL" 2>/dev/null || echo "{}")
        DB_STATUS=$(echo "$RESPONSE" | python3 -c "import sys,json; print(json.load(sys.stdin).get('database','unknown'))" 2>/dev/null || echo "unknown")

        if [[ "$DB_STATUS" == "ok" ]]; then
            log "Database connection: OK"
            log "=== Deploy successful ==="
            exit 0
        else
            log "Database status: $DB_STATUS (retrying...)"
        fi
    else
        log "Health check attempt $i/$HEALTH_RETRIES failed"
    fi
done

error "Health check failed after $HEALTH_RETRIES attempts"
exit 1
