#!/usr/bin/env bash
set -euo pipefail
# shellcheck source=_common.sh
source "$(dirname "${BASH_SOURCE[0]}")/_common.sh"

require_cmd decpki "Run: pip install -e . from the repo root"

REQUEST_ID="${1:?Usage: promote-enrolment.sh <request-id>}"
REQUEST_FILE="${ENROLMENT_DIR}/${REQUEST_ID}.json"

if [[ ! -f "$REQUEST_FILE" ]]; then
    echo "ERROR: Request file not found: ${REQUEST_FILE}" >&2
    exit 1
fi

log "Signing with alpha validator..."
decpki enrol-sign --request "$REQUEST_FILE" --validator "${KEY_DIR}/alpha.key.json"

log "Signing with beta validator..."
decpki enrol-sign --request "$REQUEST_FILE" --validator "${KEY_DIR}/beta.key.json"

log "Promoting enrolment ${REQUEST_ID}..."
decpki enrol-promote \
    --request "$REQUEST_FILE" \
    --validator "${KEY_DIR}/alpha.key.json" \
    --validator "${KEY_DIR}/beta.key.json" \
    --threshold 2

log "Regenerating trust bundle → ${BUNDLE_PATH}"
decpki bundle \
    --validator "${KEY_DIR}/alpha.key.json" \
    --validator "${KEY_DIR}/beta.key.json" \
    --validator "${KEY_DIR}/gamma.key.json" \
    --threshold 2 \
    --grace 24h \
    --out "${BUNDLE_PATH}"

log "Done. DID is now active. Log in at http://localhost:${DEMO_PORT}/login.html"
