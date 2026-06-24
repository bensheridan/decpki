#!/bin/bash
set -euo pipefail

log() { echo "[SERVER $(date -u +%H:%M:%S)] $*"; }

DEMO_DID="${DEMO_DID:-did:local:demo-server}"
BUNDLE_GRACE="${BUNDLE_GRACE:-24h}"
LOG="/tmp/identity_log.json"

log "Generating 3 validator keypairs..."
decpki --log "$LOG" keygen --name alpha --out /tmp/alpha.key.json
decpki --log "$LOG" keygen --name beta  --out /tmp/beta.key.json
decpki --log "$LOG" keygen --name gamma --out /tmp/gamma.key.json

log "Registering identity: ${DEMO_DID}"
# Generate an ephemeral keypair for the demo identity
IDENTITY_SEED=$(python3 -c "
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
import binascii
k = Ed25519PrivateKey.generate()
print(binascii.hexlify(k.public_key().public_bytes_raw()).decode())
")
decpki --log "$LOG" register \
    --did "${DEMO_DID}" \
    --pubkey "${IDENTITY_SEED}" \
    --validator /tmp/alpha.key.json \
    --validator /tmp/beta.key.json \
    --meta env=demo \
    --meta service=server

log "Generating trust bundle (grace: ${BUNDLE_GRACE})..."
decpki --log "$LOG" bundle \
    --validator /tmp/alpha.key.json \
    --validator /tmp/beta.key.json \
    --threshold 2 \
    --grace "${BUNDLE_GRACE}" \
    --out /shared/bundle.cbor

BUNDLE_SIZE=$(wc -c < /shared/bundle.cbor)
log "Bundle written to /shared/bundle.cbor (${BUNDLE_SIZE} bytes)"

# Write sentinel last, after bundle is fully flushed
date -u +%Y-%m-%dT%H:%M:%SZ > /shared/bundle.ready
log "Ready sentinel written. Exiting."
