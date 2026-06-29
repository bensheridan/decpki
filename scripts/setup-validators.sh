#!/usr/bin/env bash
set -euo pipefail
# shellcheck source=_common.sh
source "$(dirname "${BASH_SOURCE[0]}")/_common.sh"

require_cmd decpki "Run: pip install -e . from the repo root"

mkdir -p "$KEY_DIR"

for name in alpha beta gamma; do
    out="${KEY_DIR}/${name}.key.json"
    if [[ -f "$out" ]]; then
        log "${out} already exists — skipping."
    else
        log "Generating ${name} validator keypair → ${out}"
        decpki keygen --name "$name" --out "$out"
    fi
done

log "Generating trust bundle → ${BUNDLE_PATH}"
decpki bundle \
    --validator "${KEY_DIR}/alpha.key.json" \
    --validator "${KEY_DIR}/beta.key.json" \
    --validator "${KEY_DIR}/gamma.key.json" \
    --threshold 2 \
    --grace 24h \
    --out "${BUNDLE_PATH}"

log "Setup complete. Run: scripts/start-demo.sh"
