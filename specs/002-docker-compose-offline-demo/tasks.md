---
description: "Task list for Docker Compose Offline Demo"
---

# Tasks: Docker Compose Offline Demo

**Input**: Design documents from `specs/002-docker-compose-offline-demo/`

**Prerequisites**: plan.md ✅, spec.md ✅, research.md ✅, data-model.md ✅, contracts/ ✅, quickstart.md ✅

**Tests**: No automated test tasks — this is an orchestration layer validated manually against quickstart.md scenarios.

**Organization**: Tasks grouped by user story. US1 is the full MVP; US2 and US3 add on top.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Parallelizable (different files, no shared dependencies)
- **[Story]**: User story this task belongs to (US1, US2, US3)

---

## Phase 1: Setup

**Purpose**: Create the demo directory structure and base files

- [x] T001 Create `demo/` directory at repo root and add placeholder files: `demo/Dockerfile`, `demo/docker-compose.yml`, `demo/server-entrypoint.sh`, `demo/client-entrypoint.sh`
- [x] T002 [P] Create `demo.sh` at repo root (executable, `chmod +x demo.sh`) with a skeleton that prints usage and exits 1 — to be filled in later tasks
- [x] T003 [P] Add `demo/` entries to `.gitignore`: no secrets leak from key files generated inside containers (already covered by `*.key.json` pattern from feature 001)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Working Docker image that can run `decpki` CLI — MUST complete before any entrypoint scripts

**⚠️ CRITICAL**: Both entrypoints depend on this image building successfully

- [x] T004 Write `demo/Dockerfile`: base `python:3.11-slim`; copy repo root into `/app`; run `pip install -e /app` to install the `decpki` package; set `WORKDIR /app`; no `ENTRYPOINT` (set per-service in compose)
- [x] T005 Write `demo/docker-compose.yml` skeleton: define `server` service (image build from `.`, entrypoint `demo/server-entrypoint.sh`, volume `demo-shared:/shared`, env `BUNDLE_GRACE` and `DEMO_DID`); define `client` service (same image, entrypoint `demo/client-entrypoint.sh`, volume `demo-shared:/shared`, env `DEMO_DID` and `BUNDLE_PATH`, `depends_on: server: condition: service_completed_successfully`); define named volume `demo-shared`; define network `demo-net` attached to both services
- [x] T006 Verify image builds successfully: `docker compose -f demo/docker-compose.yml build` — fix any pip install or COPY errors before proceeding

**Checkpoint**: `docker compose -f demo/docker-compose.yml build` exits 0

---

## Phase 3: User Story 1 — Full Offline Verification Demo (Priority: P1) 🎯 MVP

**Goal**: Single `./demo.sh` command produces a VALID offline verification result with network cut after bundle sync

**Independent Test**: `./demo.sh` exits 0 and terminal shows `[CLIENT] VALID: did:local:demo-server is a trusted identity`

### Implementation for User Story 1

- [x] T007 [US1] Write `demo/server-entrypoint.sh`: (1) generate 3 validator keypairs to `/tmp/` using `decpki keygen`; (2) register `$DEMO_DID` with validators alpha+beta using `decpki register`; (3) generate bundle with `decpki bundle --grace $BUNDLE_GRACE --out /shared/bundle.cbor`; (4) write ISO timestamp to `/shared/bundle.ready`; (5) print `[SERVER]`-prefixed log lines at each step; (6) exit 0. Use `set -euo pipefail` at top.
- [x] T008 [US1] Write `demo/client-entrypoint.sh`: (1) wait for `/shared/bundle.cbor` to exist (poll 0.5s, max 10 attempts — should already be there since `depends_on: service_completed_successfully`); (2) print `[CLIENT] Bundle received at $BUNDLE_PATH`; (3) print `[CLIENT] Running offline verification (no network)...`; (4) run `decpki verify --bundle $BUNDLE_PATH --did $DEMO_DID`; (5) capture and print result with `[CLIENT]` prefix; (6) exit with verify's exit code. Use `set -euo pipefail`.
- [x] T009 [US1] Write `demo.sh` full implementation: (1) parse `--short-expiry`, `--no-build`, `--did` flags; (2) set `BUNDLE_GRACE` and `DEMO_DID` env vars; (3) check `docker compose version` exits 0, else print error and exit 1; (4) run `docker compose -f demo/docker-compose.yml down -v 2>/dev/null || true` to clean prior state; (5) run `docker compose -f demo/docker-compose.yml up [--build] -d server`; (6) poll for `bundle.ready` on the named volume by exec-ing into the server container's shared volume mount (use `docker run --rm -v <vol>:/shared alpine test -f /shared/bundle.ready`), 1s interval, 30s timeout, exit 1 on timeout; (7) disconnect client from network: resolve network name as `$(docker compose -f demo/docker-compose.yml ps -q server | head -1)` → use `docker inspect` to find network name → `docker network disconnect <net> <project>-client-1 2>/dev/null || true`; (8) run `docker compose -f demo/docker-compose.yml up client` (foreground, not `-d`); (9) capture client exit code; (10) print `[DEMO] Demo complete. Exit code: $exit_code`; (11) exit with client exit code.
- [x] T010 [US1] Make both entrypoint scripts executable: `chmod +x demo/server-entrypoint.sh demo/client-entrypoint.sh`
- [x] T011 [US1] Validate US1 manually: run `./demo.sh` and confirm output matches quickstart.md Standard Run expected output; confirm exit code 0; confirm `docker inspect` on client container shows empty Networks map

**Checkpoint**: `./demo.sh` exits 0 with VALID output. Quickstart Scenario 1 passes.

---

## Phase 4: User Story 2 — Expiry Demo (Priority: P2)

**Goal**: `./demo.sh --short-expiry` demonstrates EXPIRED outcome automatically after 30s grace period lapses

**Independent Test**: `./demo.sh --short-expiry` exits 5 and terminal shows `[CLIENT] EXPIRED:`

### Implementation for User Story 2

- [x] T012 [US2] Extend `demo.sh` short-expiry path: when `--short-expiry` flag is set, after the first VALID verification completes, print `[DEMO] Waiting for bundle to expire (grace: $BUNDLE_GRACE)...`; parse `BUNDLE_GRACE` (strip trailing `s`) and sleep that many seconds plus 1; then re-run the client container against the same (now expired) bundle by calling `docker compose -f demo/docker-compose.yml run --rm client`; capture and propagate exit code 5
- [x] T013 [US2] Validate US2 manually: run `./demo.sh --short-expiry` and confirm output shows VALID then EXPIRED; confirm exit code 5; confirm log lines include the wait message with correct duration

**Checkpoint**: `./demo.sh --short-expiry` exits 5 with EXPIRED output after ~31 seconds.

---

## Phase 5: User Story 3 — Observable Demo Output (Priority: P3)

**Goal**: Every stage transition has a timestamped, clearly prefixed log line that tells the trust model story

**Independent Test**: Run demo, count `[SERVER]` and `[CLIENT]` and `[DEMO]` prefixed lines — every stage listed in the quickstart.md expected output must appear

### Implementation for User Story 3

- [x] T014 [US3] Add timestamps to all log lines in `demo/server-entrypoint.sh`: prefix each `echo` with `[SERVER $(date -u +%H:%M:%S)]`; ensure log lines match the expected output in `contracts/demo-script-contract.md` exactly (stage names: "Generating 3 validator keypairs", "Registering identity", "Generating trust bundle", "Bundle written", "Ready sentinel written. Exiting.")
- [x] T015 [US3] Add timestamps to all log lines in `demo/client-entrypoint.sh`: prefix each `echo` with `[CLIENT $(date -u +%H:%M:%S)]`; ensure log lines include: "Bundle received", "Running offline verification (no network)", and the verify outcome line
- [x] T016 [US3] Add timestamps to `[DEMO]` lines in `demo.sh`: prefix with `[DEMO $(date -u +%H:%M:%S)]`; add stage lines for: "Cleaning up prior state", "Building and starting server container", "Bundle ready. Disconnecting client from network", "Network isolated. Starting client container", "Demo complete. Exit code: N"
- [x] T017 [US3] Add failure mode messages to `demo.sh` per `contracts/demo-script-contract.md`: Docker not found → print error + exit 1; server container exits non-zero → print error + exit 1; bundle sentinel timeout → print error + exit 1; network disconnect failure → print WARNING and continue (non-fatal)

**Checkpoint**: Run demo with verbose output; all stage lines appear with timestamps; failure modes tested by temporarily removing Docker and confirming error message.

---

## Phase 6: Polish

**Purpose**: Cleanup, README update, final validation

- [x] T018 [P] Add `demo/` section to top-level `README.md`: add a "## Demo" heading after the Quickstart section explaining `./demo.sh` and `./demo.sh --short-expiry` with one-line descriptions; link to `specs/002-docker-compose-offline-demo/quickstart.md` for full details
- [x] T019 [P] Add `demo/.dockerignore` to exclude from the build context: `.git/`, `specs/`, `*.key.json`, `*.cbor`, `__pycache__/`, `.pytest_cache/`, `tests/`, `decpki.egg-info/`
- [x] T020 Run all three quickstart.md validation scenarios (standard run, short-expiry run, network isolation check) and confirm all pass; document any deviations

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Depends on Phase 1 — image build blocks all entrypoints
- **US1 (Phase 3)**: Depends on Phase 2 — entrypoints need working image
- **US2 (Phase 4)**: Depends on US1 — extends `demo.sh` short-expiry path
- **US3 (Phase 5)**: Depends on US1 — adds timestamps to existing log lines
- **Polish (Phase 6)**: Depends on Phases 3, 4, 5

### Within Phase 3

- T007 (server entrypoint) and T008 (client entrypoint) can run in parallel — different files
- T009 (`demo.sh`) depends on T007 and T008 being conceptually complete (it calls them)
- T010 (chmod) depends on T007 and T008
- T011 (manual validation) depends on T009 and T010

### Parallel Opportunities

```bash
# Phase 1:
T001  |  T002  |  T003   (all different files)

# Phase 3:
T007 server-entrypoint.sh  |  T008 client-entrypoint.sh

# Phase 5:
T014 server timestamps  |  T015 client timestamps  |  T016 demo.sh timestamps

# Phase 6:
T018 README update  |  T019 .dockerignore
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1 (Setup)
2. Complete Phase 2 (Foundational — working image)
3. Complete Phase 3 (US1 — full offline demo)
4. **STOP and VALIDATE**: Run `./demo.sh`, confirm VALID exit 0
5. Ship MVP: offline guarantee demonstrated

### Incremental Delivery

1. Setup + Foundational → image builds
2. US1 complete → `./demo.sh` exits 0 (MVP)
3. US2 complete → `./demo.sh --short-expiry` exits 5
4. US3 complete → timestamped stage output
5. Polish → README, .dockerignore, final validation

---

## Notes

- `[P]` = different files, no shared in-flight dependencies
- The named volume `demo-shared` is the ONLY data channel — never add ad-hoc networking after bundle sync
- Network name resolution: `docker compose -f demo/docker-compose.yml ps --format json` gives project name; network is `<project>_demo-net`
- `set -euo pipefail` is REQUIRED in all bash scripts — prevents silent failures in the demo
- The `depends_on: service_completed_successfully` condition means the client never starts if the server exits non-zero; the client entrypoint polling loop is a safety net only
- `docker compose run --rm client` (US2 re-run) creates a fresh container instance against the existing shared volume — the expired bundle is still there
