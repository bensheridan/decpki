# Data Model: Docker Compose Offline Demo

This feature is an orchestration layer over the existing `decpki` library. The data entities
are files and environment signals exchanged between containers via the shared volume and
the Docker network. There are no new persistent data structures.

---

## Shared Volume File Contracts

### `/shared/bundle.cbor`

The signed trust bundle produced by the server. Binary CBOR format defined in
[feature 001 data-model](../001-bundle-format-validator-quorum/data-model.md).

| Attribute   | Value |
|-------------|-------|
| Written by  | Server container entrypoint (`server-entrypoint.sh`) |
| Read by     | Client container entrypoint (`client-entrypoint.sh`) |
| Format      | CBOR binary (`.cbor`) |
| Lifecycle   | Created on server startup; deleted on `docker compose down -v` |

### `/shared/bundle.ready`

Sentinel file written by the server after `bundle.cbor` is fully flushed to disk. Its
presence signals to the orchestrator that the bundle is safe to use.

| Attribute   | Value |
|-------------|-------|
| Content     | Plain text: ISO timestamp of bundle generation |
| Written by  | Server entrypoint (after `bundle.cbor` write completes) |
| Read by     | `demo.sh` orchestrator (polls with 1s interval, 30s timeout) |
| Lifecycle   | Same as `bundle.cbor` |

---

## Environment Variables

### Server Container

| Variable       | Default | Description |
|----------------|---------|-------------|
| `BUNDLE_GRACE` | `24h`   | Grace period passed to `decpki bundle --grace`. Format: `24h`, `7d`, `30s`. |
| `DEMO_DID`     | `did:local:demo-server` | DID registered by the server. |

### Client Container

| Variable       | Default | Description |
|----------------|---------|-------------|
| `DEMO_DID`     | `did:local:demo-server` | DID to verify against the bundle. Must match server. |
| `BUNDLE_PATH`  | `/shared/bundle.cbor`   | Path to the bundle file inside the container. |

---

## Container Lifecycle States

### Server Container

```
STARTING
  └── generate validator keypairs (3 nodes, in-process)
  └── register DEMO_DID with 2-of-3 quorum
  └── generate bundle (grace = BUNDLE_GRACE)
  └── write /shared/bundle.cbor
  └── write /shared/bundle.ready
EXITED (code 0)
```

### Client Container

```
STARTING (depends on server: service_completed_successfully)
  └── wait for /shared/bundle.cbor (should already exist)
  └── log: "[CLIENT] Bundle received — network isolation about to begin"
  └── [network already disconnected by demo.sh before this point]
  └── run: decpki verify --bundle /shared/bundle.cbor --did $DEMO_DID
  └── log: "[CLIENT] <outcome message>"
EXITED (code = verify exit code)
```

### Orchestrator (`demo.sh`)

```
1. docker compose down -v            # clean prior state
2. docker compose up --build -d server
3. poll /shared/bundle.ready (1s interval, 30s timeout)
4. docker network disconnect <net> <client-container>  [no-op if client not yet started]
5. docker compose up client          # client starts with network already gone
6. propagate client exit code
```

---

## Docker Compose Service Graph

```
demo-shared (volume)
     │
     ├── server (writes bundle.cbor, bundle.ready → exits 0)
     │
     └── client (reads bundle.cbor → verifies → exits with verify code)
              depends_on: server (service_completed_successfully)

demo-net (network) — connected to server during startup only
                   — disconnected from client by demo.sh before client starts
```
