# Implementation Plan: Docker Compose Offline Demo

**Branch**: `002-docker-compose-offline-demo` | **Date**: 2026-06-24 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/002-docker-compose-offline-demo/spec.md`

## Summary

A two-container Docker Compose demo that proves the offline guarantee of the `decpki` trust
bundle. A server container generates a signed bundle and writes it to a shared volume; the
orchestrator script cuts the network; a client container verifies the identity with zero
network calls. A short-expiry mode demonstrates the revocation path without a long wait.

## Technical Context

**Language/Version**: Bash (entrypoint scripts, `demo.sh`); Python 3.11 (container runtime via existing `decpki` library)

**Primary Dependencies**: Docker Engine + Compose V2 (host); `decpki` library (feature 001, already implemented)

**Storage**: Docker named volume `demo-shared` — carries `bundle.cbor` and `bundle.ready` between containers

**Testing**: Manual validation against quickstart.md scenarios; no automated tests added (orchestration layer)

**Target Platform**: Linux/macOS host with Docker Engine; containers run Python 3.11-slim

**Project Type**: Demo / orchestration wrapper

**Performance Goals**: Full demo (build + run) completes in under 60 seconds after first build; subsequent runs (`--no-build`) in under 10 seconds

**Constraints**: No host dependencies beyond Docker Compose V2; single-host only; no privileged container capabilities

**Scale/Scope**: Single demo identity; 3-node in-process quorum; two containers

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Gate | Status |
|-----------|------|--------|
| I. Decentralized Trust | Demo uses the same 2-of-3 quorum signing path as feature 001 | ✅ Pass |
| II. Offline-First Verification | Network literally disconnected before client verification runs | ✅ Pass — physically enforced, not just logical |
| III. Cryptographic Auditability | Bundle format unchanged from feature 001; no new trust mechanisms | ✅ Pass |
| IV. Minimal Credential Surface | No new credential types; demo uses `did:local:demo-server` + ed25519 | ✅ Pass |
| V. Explicit Revocation Policy | Short-expiry mode explicitly demonstrates Option B; grace period is configurable | ✅ Pass |
| VI. Validator Quorum Governance | In-process 3-node quorum used; threshold=2 enforced same as feature 001 | ✅ Pass |

No violations. No Complexity Tracking table needed.

## Project Structure

### Documentation (this feature)

```text
specs/002-docker-compose-offline-demo/
├── plan.md           # This file
├── research.md       # Phase 0 output
├── data-model.md     # Volume/env/lifecycle contracts
├── quickstart.md     # Validation guide
├── contracts/
│   └── demo-script-contract.md   # demo.sh interface + compose file contract
└── tasks.md          # Phase 2 output (/speckit-tasks — not yet created)
```

### Source Code (repository root)

```text
demo/
├── Dockerfile                # Single image for both server and client containers
├── docker-compose.yml        # Service definitions: server, client, volume, network
├── server-entrypoint.sh      # Bash: keygen → register → bundle → write sentinel → exit 0
└── client-entrypoint.sh      # Bash: wait for bundle → log ready → run decpki verify → exit

demo.sh                       # Top-level orchestrator:
                              #   down -v → up server → poll sentinel →
                              #   network disconnect → up client → propagate exit code
```

**Structure Decision**: All demo files live under `demo/` to keep them isolated from the
`src/decpki/` library. `demo.sh` lives at the repo root for easy discoverability (`./demo.sh`).
The same `Dockerfile` is used for both containers (different entrypoints via compose config).
