# Research: Docker Compose Offline Demo

## Decision 1: Network Isolation Mechanism

**Decision**: Host-side orchestrator script calls `docker network disconnect` after detecting
bundle readiness, then re-attaches nothing — the client container proceeds with no network.

**Rationale**: This approach produces the clearest observable narrative: two containers start
connected, the orchestrator cuts the wire, the client verifies offline. The `docker network
disconnect` command is idempotent and takes effect immediately. It requires the Docker CLI on
the host (always present when Docker Compose is available) and does not require `NET_ADMIN`
capability inside the container.

**Readiness signal**: The server writes a sentinel file `bundle.ready` to the shared volume
alongside `bundle.cbor`. The orchestrator polls for this file (1-second interval, 30-second
timeout) before disconnecting the network.

**Alternatives considered**:
- `NET_ADMIN` + `ip link set eth0 down` inside the client: Works but requires a privileged
  capability, which is a security concern in demo environments.
- `--network none` from the start + pre-staged bundle: Loses the "sync then cut" story that
  makes the demo convincing.
- Docker Compose `network` with firewall rules: Overcomplicated for a demo.

---

## Decision 2: Bundle Transfer Mechanism

**Decision**: Docker named volume (`demo-shared`) mounted at `/shared` in both containers.
Server writes `bundle.cbor` and `bundle.ready` to `/shared/`. Client polls for `bundle.ready`.

**Rationale**: Named volumes are the standard Docker pattern for container-to-container file
exchange. They work across container restarts (important for the repeatable demo requirement)
and are emptied on `docker compose down -v`, ensuring a clean state each run.

**Alternative considered**: HTTP file transfer over the compose network — more realistic but
more setup, and the bundle is already a file so volume sharing is the simpler fit.

---

## Decision 3: Startup Orchestration

**Decision**: Two-phase orchestration via `demo.sh` wrapper script at repo root.

Phase 1 — compose up:
```
docker compose up --build -d server
# wait for bundle.ready on shared volume
docker network disconnect demo_demo-net demo-client  # cut the wire
docker compose up --build client  # client runs with no network
```

The server container is brought up first. The orchestrator watches the shared volume for
`bundle.ready`, then disconnects the client from the network and starts the client container.
The client container's network is disconnected before it starts, so it never had connectivity
in the first place — which actually makes the demo even cleaner.

**Alternative timing**: Start both containers simultaneously, disconnect mid-run. This is
harder to orchestrate reliably (race condition between sync and disconnect). Sequential
startup is simpler and equally convincing.

---

## Decision 4: Server Container Lifetime

**Decision**: Server container exits with code 0 after writing bundle and sentinel to the
shared volume. It does not stay alive as a persistent service.

**Rationale**: The demo is proving offline verification — there is no reason for the server
to remain up after bundle generation. Exiting cleanly also avoids compose keeping the demo
running indefinitely.

**Compose dependency**: `client` has `depends_on: server: condition: service_completed_successfully`
so compose waits for the server to exit cleanly before starting the client.

---

## Decision 5: Grace Period Configuration

**Decision**: `BUNDLE_GRACE` environment variable, format accepted by `decpki bundle --grace`
(e.g. `24h`, `7d`, `30s`). Default: `24h`. Passed through from host to server container via
compose env file or `--env` flag.

**Short-expiry demo**: Set `BUNDLE_GRACE=30s` (or pass `--short-expiry` flag to `demo.sh`
which sets it). The demo script sleeps `BUNDLE_GRACE` seconds after verification, then re-runs
the client against the now-expired bundle to show the EXPIRED outcome.

---

## Decision 6: Demo Identity

**Decision**: The server registers a single fixed demo identity: `did:local:demo-server`
with a freshly generated ed25519 keypair at startup. The private key is kept inside the
container (never exposed). The public key is embedded in the bundle.

**Rationale**: A fixed, memorable DID makes the demo output easy to follow. The key is
ephemeral (generated at container start), matching the prototype scope.

---

## Decision 7: Repeatable Runs

**Decision**: `demo.sh` runs `docker compose down -v` before each run to remove named
volumes and any leftover state. Container images are rebuilt on each run (`--build` flag)
unless `--no-build` is passed.

---

## Summary: Resolved Technical Context

| Field              | Value |
|--------------------|-------|
| Orchestration      | `demo.sh` bash script + Docker Compose V2 |
| Server image       | Python 3.11-slim, runs `decpki` library |
| Client image       | Python 3.11-slim, runs `decpki verify` |
| Volume             | Named volume `demo-shared`, mounted at `/shared` |
| Network isolation  | `docker network disconnect` called by `demo.sh` after `bundle.ready` sentinel |
| Grace period       | `BUNDLE_GRACE` env var, default `24h` |
| Demo identity      | `did:local:demo-server` (ephemeral keypair) |
| Repeatability      | `docker compose down -v` before each run |
| Dependencies       | Docker Engine + Compose V2 on host; `decpki` source in repo |
