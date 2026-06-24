# Feature Specification: Docker Compose Offline Demo

**Feature Branch**: `002-docker-compose-offline-demo`

**Created**: 2026-06-24

**Status**: Draft

**Input**: User description: "Docker Compose (two containers) — server container and client container
with the network disabled after bundle sync, which actually demonstrates the offline guarantee in a
realistic way. More setup but proves the core claim convincingly."

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Full Offline Verification Demo (Priority: P1)

A developer runs a single command that stands up two containers: a server (which holds a registered
identity) and a client (which verifies that identity). After the trust bundle is synced from server
to client, the network between them is cut. The client then verifies the server's identity
successfully with no network connectivity, proving the offline guarantee.

**Why this priority**: This is the entire point of the demo. If this scenario doesn't work, nothing
else matters.

**Independent Test**: Run `docker compose up`. Observe output showing: (1) bundle sync succeeded,
(2) network disabled, (3) verification result is VALID with no network calls. Exit code 0.

**Acceptance Scenarios**:

1. **Given** the demo is started with a single command, **When** both containers finish initialising,
   **Then** the server has a registered identity and a signed trust bundle, and the client has
   received that bundle.

2. **Given** the client has a trust bundle, **When** the network between server and client is
   disabled, **Then** the client can still verify the server's identity and prints a clear VALID
   result.

3. **Given** the network is disabled, **When** the client runs verification, **Then** no outbound
   network calls are made (verified by the fact that the network interface is down and verification
   still succeeds).

---

### User Story 2 — Revocation / Expiry Demo (Priority: P2)

The same demo environment can be used to show the bundle expiry (revocation) mechanism. The bundle
is generated with a short grace period; after it lapses, the client reports the bundle as expired
and refuses to verify — even though the network is still down.

**Why this priority**: Expiry enforcement is the revocation story. Showing it in the composed
environment makes the tradeoff (offline lag = bundle expiry window) tangible and observable.

**Independent Test**: Set a short bundle expiry (e.g. 30 seconds) via an environment variable,
wait for it to lapse, re-run the client verification — output must show EXPIRED, exit code 5.

**Acceptance Scenarios**:

1. **Given** the demo is started with a short bundle expiry configured, **When** the expiry window
   elapses, **Then** running client verification returns EXPIRED with the expiry timestamp printed.

2. **Given** an expired bundle, **When** the server issues a fresh bundle and the client syncs it,
   **Then** the client can verify again and returns VALID.

---

### User Story 3 — Observable Demo Output (Priority: P3)

Every stage of the demo emits clear, human-readable log lines so an observer watching the terminal
can follow the trust model in real time without reading source code.

**Why this priority**: The demo is a communication artifact as much as a technical one. A developer
showing this to a stakeholder needs the output to tell the story on its own.

**Independent Test**: Run the demo with verbose output enabled. Confirm log lines appear for each
stage: validator setup, identity registration, bundle generation, bundle transfer, network isolation,
verification result.

**Acceptance Scenarios**:

1. **Given** the demo is running, **When** each stage completes, **Then** a timestamped log line
   names the stage and its outcome (e.g. `[SERVER] Bundle generated — 1 identity, expires in 24h`,
   `[CLIENT] Network isolated`, `[CLIENT] VALID — did:local:payments-svc`).

2. **Given** the demo fails at any stage, **Then** the failure is reported with a clear error
   message and a non-zero exit code, making root cause obvious without reading logs.

---

### Edge Cases

- What if the server container fails to start or generate a bundle? The client must not proceed
  to the verification step and must report the dependency failure clearly.
- What if the bundle file transfer between containers fails? The demo must detect this and halt
  with an explanation rather than producing a misleading VALID or NOT FOUND result.
- What if Docker is not installed or the required version is not available? The startup script
  must check prerequisites and print a clear error before attempting anything.
- What if the grace period is set to zero or a negative value? The system must reject the
  configuration and explain the constraint.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: A single top-level command (e.g. `docker compose up` or a thin wrapper script)
  MUST stand up the full two-container environment without any manual steps beyond configuration.
- **FR-002**: The server container MUST generate validator keypairs, register at least one
  identity, and produce a signed trust bundle as part of its startup sequence.
- **FR-003**: The client container MUST receive the trust bundle from the server before the
  network is disabled. The transfer mechanism MUST be explicit and logged.
- **FR-004**: After bundle sync, the network connection between the server and client containers
  MUST be disabled. The client MUST then verify the server's identity using only the local bundle.
- **FR-005**: The verification result MUST be printed to the terminal with a clear VALID / EXPIRED
  / TAMPERED / NOT FOUND outcome and the appropriate exit code.
- **FR-006**: The bundle grace period MUST be configurable via an environment variable
  (e.g. `BUNDLE_GRACE`) without rebuilding the containers.
- **FR-007**: The demo MUST be repeatable — running it a second time MUST produce the same outcome
  as the first run, with no leftover state from a previous run causing failures.
- **FR-008**: The demo MUST include a short-expiry mode (configurable grace period ≤ 60 seconds)
  that demonstrates the expiry / revocation path without requiring the observer to wait long.
- **FR-009**: The demo MUST work on any machine with a compatible container runtime and
  `docker compose` (V2) installed, with no additional dependencies.
- **FR-010**: All inter-container data exchange (the trust bundle file) MUST use a shared volume
  or an equivalent explicit mechanism — no ad-hoc networking after the isolation step.

### Key Entities

- **ServerContainer**: Runs the validator quorum (in-process, 3 nodes), registers the demo
  identity, generates and signs the trust bundle, writes it to the shared volume, then idles.
- **ClientContainer**: Waits for the bundle to appear on the shared volume, confirms receipt,
  signals that the network can be disabled, performs offline verification, and exits with the
  appropriate code.
- **SharedVolume**: A container volume that carries the trust bundle from server to client.
  This is the only data channel between the two containers after the isolation step.
- **DemoOrchestrator**: The compose file and optional wrapper script that coordinates startup
  order, network isolation, and exit code propagation.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A developer unfamiliar with the project can run the full demo from a clean checkout
  in under 5 minutes, including container build time.
- **SC-002**: The demo completes end-to-end (server up → bundle synced → network cut → verified)
  in under 60 seconds after containers are running.
- **SC-003**: Every stage transition is logged; an observer reading only the terminal output can
  describe the trust model in their own words after watching one run.
- **SC-004**: The short-expiry mode (≤ 60 second bundle) demonstrates the EXPIRED outcome without
  any manual intervention — the demo orchestrates the wait automatically.
- **SC-005**: The demo exits with code 0 when verification succeeds and a documented non-zero code
  when verification fails, making it usable as a CI smoke test.

## Assumptions

- Docker Engine with Compose V2 (`docker compose`, not `docker-compose`) is installed on the host.
- The `decpki` library (feature 001) is already implemented and available in the repository; the
  containers build from the existing source tree.
- The demo uses an in-process 3-node validator quorum (same as the library prototype) — no
  separate validator processes or external chain.
- Network isolation is implemented by removing the container from the shared Docker network after
  bundle sync (using a compose lifecycle hook or an orchestrator script) — this is a demonstration
  mechanism, not a production security boundary.
- The demo is single-host (both containers on one machine). Multi-host networking is out of scope.
- No web UI is included; all output is to the terminal (stdout/stderr).
- The server container does not need to remain running after bundle generation; it may exit cleanly
  once the bundle is written to the shared volume.
- Authentication between server and client containers is out of scope — the demo focuses on the
  trust bundle mechanism, not transport security.
