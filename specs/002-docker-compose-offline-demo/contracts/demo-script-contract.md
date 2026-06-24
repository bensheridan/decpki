# Contract: `demo.sh` Orchestrator Script

`demo.sh` is the single entry point for the demo. It wraps Docker Compose and manages
the network isolation lifecycle.

---

## Usage

```bash
./demo.sh [--short-expiry] [--no-build] [--did <did>]
```

| Flag             | Default | Description |
|------------------|---------|-------------|
| `--short-expiry` | off     | Sets `BUNDLE_GRACE=30s` to demonstrate bundle expiry quickly |
| `--no-build`     | off     | Skip image rebuild (use cached images) |
| `--did DID`      | `did:local:demo-server` | DID to register and verify |

---

## Environment Variables (override defaults)

| Variable       | Default | Description |
|----------------|---------|-------------|
| `BUNDLE_GRACE` | `24h`   | Bundle validity window; overridden by `--short-expiry` |
| `DEMO_DID`     | `did:local:demo-server` | Demo identity DID |

---

## Exit Codes

| Code | Meaning |
|------|---------|
| 0    | Verification succeeded (VALID) |
| 1    | Script-level failure (Docker not found, timeout waiting for bundle, etc.) |
| 4    | DID not found in bundle |
| 5    | Bundle expired |
| 6    | Bundle tampered |
| 7    | Merkle proof invalid |
| 8    | Quorum not met |

Codes 4–8 are propagated directly from `decpki verify`.

---

## Expected Terminal Output (normal run)

```
[DEMO] Cleaning up prior state...
[DEMO] Building and starting server container...
[SERVER] Generating 3 validator keypairs...
[SERVER] Registering identity: did:local:demo-server
[SERVER] Generating trust bundle (grace: 24h)...
[SERVER] Bundle written to /shared/bundle.cbor (1.2 KB)
[SERVER] Ready sentinel written. Exiting.
[DEMO] Bundle ready. Disconnecting client from network...
[DEMO] Network isolated. Starting client container...
[CLIENT] Bundle received at /shared/bundle.cbor
[CLIENT] Running offline verification (no network)...
[CLIENT] VALID: did:local:demo-server is a trusted identity
[DEMO] Demo complete. Exit code: 0
```

---

## Expected Terminal Output (short-expiry run)

```
[DEMO] Short-expiry mode: BUNDLE_GRACE=30s
... (same as above through VALID) ...
[DEMO] Waiting 31 seconds for bundle to expire...
[CLIENT] Running offline verification (no network)...
[CLIENT] EXPIRED: bundle expired at 2026-06-24T12:00:30Z
[DEMO] Demo complete (expiry demonstrated). Exit code: 5
```

---

## Failure Modes

| Failure | Output | Exit code |
|---------|--------|-----------|
| Docker not installed | `[DEMO] ERROR: docker not found. Install Docker Engine with Compose V2.` | 1 |
| Server container fails | `[DEMO] ERROR: server container exited with non-zero code.` | 1 |
| Bundle not ready within 30s | `[DEMO] ERROR: timed out waiting for bundle.ready sentinel.` | 1 |
| Network disconnect fails | `[DEMO] WARNING: network disconnect failed — verification may not be truly offline.` | (continues) |

---

## Compose File Contract

The `docker-compose.yml` in the `demo/` directory defines:

```yaml
services:
  server:
    build: .
    entrypoint: /app/demo/server-entrypoint.sh
    volumes:
      - demo-shared:/shared
    environment:
      - BUNDLE_GRACE=${BUNDLE_GRACE:-24h}
      - DEMO_DID=${DEMO_DID:-did:local:demo-server}
    networks:
      - demo-net

  client:
    build: .
    entrypoint: /app/demo/client-entrypoint.sh
    volumes:
      - demo-shared:/shared
    environment:
      - DEMO_DID=${DEMO_DID:-did:local:demo-server}
      - BUNDLE_PATH=/shared/bundle.cbor
    networks:
      - demo-net
    depends_on:
      server:
        condition: service_completed_successfully

volumes:
  demo-shared:

networks:
  demo-net:
```

The `demo-net` network name determines what `demo.sh` passes to `docker network disconnect`.
The script resolves the full network name as `<compose-project-name>_demo-net`.
