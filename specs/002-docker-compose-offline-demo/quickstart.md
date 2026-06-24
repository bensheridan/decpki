# Quickstart: Docker Compose Offline Demo

**Goal**: Prove offline identity verification in a realistic two-container environment.
Total time from clean checkout: under 5 minutes.

**Prerequisites**:
- Docker Engine with Compose V2 (`docker compose version` must print v2.x or later)
- Repository checked out with the `decpki` library already implemented (feature 001)

---

## Standard Run (24-hour bundle)

```bash
./demo.sh
```

**Expected output**:
```
[DEMO] Cleaning up prior state...
[DEMO] Building and starting server container...
[SERVER] Generating 3 validator keypairs...
[SERVER] Registering identity: did:local:demo-server
[SERVER] Generating trust bundle (grace: 24h)...
[SERVER] Bundle written to /shared/bundle.cbor
[SERVER] Ready sentinel written. Exiting.
[DEMO] Bundle ready. Disconnecting client from network...
[DEMO] Network isolated. Starting client container...
[CLIENT] Bundle received at /shared/bundle.cbor
[CLIENT] Running offline verification (no network)...
[CLIENT] VALID: did:local:demo-server is a trusted identity
[DEMO] Demo complete. Exit code: 0
```

Exit code: `0`

---

## Short-Expiry Run (demonstrates revocation / expiry)

```bash
./demo.sh --short-expiry
```

This sets `BUNDLE_GRACE=30s`. After the VALID result, the script waits 31 seconds
then re-runs the client against the now-expired bundle.

**Expected additional output**:
```
[DEMO] Waiting 31 seconds for bundle to expire...
[CLIENT] EXPIRED: bundle expired at <timestamp>
[DEMO] Demo complete (expiry demonstrated). Exit code: 5
```

Exit code: `5`

---

## Validation Scenarios

### Scenario 1 — Confirm network is truly isolated

After the client prints VALID, inspect the client container's network interfaces:

```bash
docker inspect demo-client --format '{{json .NetworkSettings.Networks}}'
# Expected: {} (empty — no networks attached)
```

### Scenario 2 — Tamper detection

After a standard run, flip a byte in the bundle and re-run the client:

```bash
python3 -c "
data = open('/var/lib/docker/volumes/pki-design_demo-shared/_data/bundle.cbor', 'rb').read()
data = data[:100] + bytes([data[100] ^ 0xFF]) + data[101:]
open('/var/lib/docker/volumes/pki-design_demo-shared/_data/bundle.cbor', 'wb').write(data)
"
docker compose -f demo/docker-compose.yml run --rm client
# Expected: TAMPERED — exit code 6
```

(Volume path may vary; adjust for your Docker data root.)

### Scenario 3 — Quorum failure

Set threshold higher than number of validators to observe the quorum failure path.
This is a unit-test-level check rather than a compose scenario — see
[feature 001 quickstart](../001-bundle-format-validator-quorum/quickstart.md) Scenario B.

---

## Project Layout (this feature)

```text
demo/
├── docker-compose.yml        # Compose service definitions
├── Dockerfile                # Shared image for server and client
├── server-entrypoint.sh      # Server startup script
└── client-entrypoint.sh      # Client verification script

demo.sh                       # Top-level orchestrator (run this)
```

See [data-model.md](data-model.md) for the volume and environment variable contracts,
and [contracts/demo-script-contract.md](contracts/demo-script-contract.md) for the
full `demo.sh` interface specification.
