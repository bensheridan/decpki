#!/bin/bash
set -euo pipefail

log() { echo "[CLIENT $(date -u +%H:%M:%S)] $*"; }

DEMO_DID="${DEMO_DID:-did:local:demo-server}"
BUNDLE_PATH="${BUNDLE_PATH:-/shared/bundle.cbor}"

# Safety poll — bundle should already be present (server exited successfully)
MAX_ATTEMPTS=10
attempt=0
until [ -f "${BUNDLE_PATH}" ]; do
    attempt=$((attempt + 1))
    if [ "${attempt}" -ge "${MAX_ATTEMPTS}" ]; then
        log "ERROR: bundle not found at ${BUNDLE_PATH} after ${MAX_ATTEMPTS} attempts"
        exit 1
    fi
    sleep 0.5
done

log "Bundle received at ${BUNDLE_PATH}"
log "Running offline verification (no network)..."

# Run verify and capture output + exit code
set +e
RESULT=$(decpki verify --bundle "${BUNDLE_PATH}" --did "${DEMO_DID}" 2>&1)
EXIT_CODE=$?
set -e

log "${RESULT}"
exit "${EXIT_CODE}"
