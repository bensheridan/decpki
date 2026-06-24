#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COMPOSE_FILE="${SCRIPT_DIR}/demo/docker-compose.yml"

# Defaults
BUNDLE_GRACE="${BUNDLE_GRACE:-24h}"
DEMO_DID="${DEMO_DID:-did:local:demo-server}"
SHORT_EXPIRY=0
NO_BUILD=0

log() { echo "[DEMO $(date -u +%H:%M:%S)] $*"; }

usage() {
    echo "Usage: $0 [--short-expiry] [--no-build] [--did <did>]"
    echo ""
    echo "  --short-expiry    Set BUNDLE_GRACE=30s to demonstrate bundle expiry"
    echo "  --no-build        Skip container image rebuild"
    echo "  --did DID         DID to register and verify (default: did:local:demo-server)"
    exit 1
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --short-expiry) SHORT_EXPIRY=1; BUNDLE_GRACE="30s"; shift ;;
        --no-build)     NO_BUILD=1; shift ;;
        --did)          DEMO_DID="$2"; shift 2 ;;
        -h|--help)      usage ;;
        *) echo "Unknown flag: $1"; usage ;;
    esac
done

export BUNDLE_GRACE
export DEMO_DID

# Prerequisite check
if ! docker compose version &>/dev/null; then
    log "ERROR: docker not found. Install Docker Engine with Compose V2."
    exit 1
fi

if [ "${SHORT_EXPIRY}" -eq 1 ]; then
    log "Short-expiry mode: BUNDLE_GRACE=${BUNDLE_GRACE}"
fi

log "Cleaning up prior state..."
docker compose -f "${COMPOSE_FILE}" down -v 2>/dev/null || true

BUILD_FLAG="--build"
if [ "${NO_BUILD}" -eq 1 ]; then
    BUILD_FLAG=""
fi

log "Building and starting server container..."
# shellcheck disable=SC2086
docker compose -f "${COMPOSE_FILE}" up ${BUILD_FLAG} -d server

# Compose project name defaults to the directory containing the compose file ("demo")
COMPOSE_PROJECT=$(basename "$(dirname "${COMPOSE_FILE}")")
VOLUME_NAME="${COMPOSE_PROJECT}_demo-shared"
NETWORK_NAME="${COMPOSE_PROJECT}_demo-net"

# Poll for bundle.ready sentinel via a throwaway alpine container
log "Waiting for server to generate bundle..."
MAX_WAIT=60
elapsed=0
until docker run --rm -v "${VOLUME_NAME}:/shared" alpine:3.19 test -f /shared/bundle.ready 2>/dev/null; do
    elapsed=$((elapsed + 1))
    if [ "${elapsed}" -ge "${MAX_WAIT}" ]; then
        log "ERROR: timed out waiting for bundle.ready sentinel after ${MAX_WAIT}s"
        docker compose -f "${COMPOSE_FILE}" logs server
        exit 1
    fi
    sleep 1
done

# Ensure server has fully exited
docker compose -f "${COMPOSE_FILE}" wait server 2>/dev/null || true

log "Bundle ready. Disconnecting client from network (no-op if client not yet started)..."
# Container name is <project>-client-1 where project = compose directory name
docker network disconnect "${NETWORK_NAME}" "${COMPOSE_PROJECT}-client-1" 2>/dev/null \
    && log "Network connection removed." \
    || log "Network disconnect skipped — client not yet on network (expected)."

log "Network isolated. Starting client container..."
set +e
# --no-deps: server already ran and succeeded (verified via sentinel); skip compose dependency management
docker compose -f "${COMPOSE_FILE}" run --no-deps --rm client
CLIENT_EXIT=$?
set -e

log "Demo complete. Exit code: ${CLIENT_EXIT}"

if [ "${SHORT_EXPIRY}" -eq 1 ] && [ "${CLIENT_EXIT}" -eq 0 ]; then
    GRACE_SECS=$(echo "${BUNDLE_GRACE}" | sed 's/s$//')
    WAIT_SECS=$((GRACE_SECS + 1))
    log "Waiting ${WAIT_SECS} seconds for bundle to expire (grace: ${BUNDLE_GRACE})..."
    sleep "${WAIT_SECS}"
    log "Re-running client against expired bundle..."
    set +e
    docker compose -f "${COMPOSE_FILE}" run --no-deps --rm client
    CLIENT_EXIT=$?
    set -e
    log "Demo complete (expiry demonstrated). Exit code: ${CLIENT_EXIT}"
fi

exit "${CLIENT_EXIT}"
