# Tasks: Quickstart Scripts

**Input**: Design documents from `specs/009-quickstart-scripts/`

**Prerequisites**: plan.md, spec.md, research.md, contracts/scripts.md, quickstart.md

**Organization**: Tasks grouped by user story. Each script is independently testable.
No tests are included (shell scripts; manual validation via quickstart.md scenarios).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[US#]**: User story this task belongs to

---

## Phase 1: Setup

**Purpose**: Create the `scripts/` directory and a shared helper library used by all scripts.

- [X] T001 Create `scripts/` directory at repo root and add `scripts/_common.sh` containing: `require_cmd()` helper, `log()` helper, default env var values (`KEY_DIR`, `BUNDLE_PATH`, `ENROLMENT_DIR`, `BFF_PORT`, `DEMO_PORT`), and `REPO_ROOT` resolution via `$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)`
- [X] T002 Add `set -euo pipefail` and `source "$(dirname "${BASH_SOURCE[0]}")/_common.sh"` boilerplate pattern (documented in `_common.sh` header comment so each script knows how to include it)

---

## Phase 2: Foundational (No additional prerequisites)

There is no blocking infrastructure beyond Phase 1 — each script is standalone. All user story phases can proceed after T001–T002 complete.

**Checkpoint**: `scripts/_common.sh` exists and is sourced correctly. Proceed to user story phases.

---

## Phase 3: User Story 1 — Start the Full Demo Stack (Priority: P1) 🎯 MVP

**Goal**: `scripts/start-demo.sh` starts BFF + browser server concurrently, handles port conflicts and missing secrets, and shuts down cleanly on Ctrl-C.

**Independent Test**: From repo root, run `bash scripts/start-demo.sh`; within 5 seconds `curl -s http://localhost:8000/docs` and `curl -s http://localhost:3000/register.html` both return 200. Then Ctrl-C; `ps aux | grep uvicorn` returns nothing.

- [X] T003 [US1] Create `scripts/start-demo.sh`: add shebang (`#!/usr/bin/env bash`), `set -euo pipefail`, source `_common.sh`, parse `--bff-port` and `--demo-port` flags overriding `BFF_PORT`/`DEMO_PORT`
- [X] T004 [US1] Add prerequisite checks to `scripts/start-demo.sh`: call `require_cmd python3`, `require_cmd node`, `require_cmd uvicorn`, `require_cmd decpki` with actionable error messages per the contract in `contracts/scripts.md`
- [X] T005 [US1] Add port conflict detection to `scripts/start-demo.sh`: use `lsof -i :$BFF_PORT -sTCP:LISTEN -t` and `lsof -i :$DEMO_PORT -sTCP:LISTEN -t`; if either occupied, print the error format from `contracts/scripts.md` and exit 1; if `lsof` is not installed, print a warning and skip the check
- [X] T006 [US1] Add `SESSION_SECRET` auto-generation to `scripts/start-demo.sh`: if `SESSION_SECRET` is unset or empty, generate with `openssl rand -hex 32`, export it, and print a warning that it is ephemeral and not suitable for production
- [X] T007 [US1] Add process-group shutdown trap to `scripts/start-demo.sh`: `trap 'kill 0' EXIT INT TERM` placed before any child processes are launched
- [X] T008 [US1] Launch BFF and browser demo server as background processes in `scripts/start-demo.sh`: `cd "$REPO_ROOT/bff" && SESSION_SECRET="$SESSION_SECRET" BFF_STORE_PATH="${BFF_STORE_PATH:-/tmp/decpki-bff.db}" BUNDLE_PATH="$BUNDLE_PATH" uvicorn main:app --port "$BFF_PORT" &` and `BUNDLE_PATH="$BUNDLE_PATH" PORT="$DEMO_PORT" BFF_PORT="$BFF_PORT" node "$REPO_ROOT/browser/demo/server.mjs" &`
- [X] T009 [US1] Print startup URLs and `wait` in `scripts/start-demo.sh`: after launching both processes, print the three lines from `contracts/scripts.md` (`[decpki] BFF listening at ...`, `[decpki] Demo server listening at ...`, `[decpki] Press Ctrl-C to stop.`), then call `wait` to block until children exit
- [X] T010 [US1] Make `scripts/start-demo.sh` executable: `chmod +x scripts/start-demo.sh`

**Checkpoint**: `bash scripts/start-demo.sh` starts both servers, URLs print, Ctrl-C stops everything cleanly with no orphan processes.

---

## Phase 4: User Story 2 — Validator Setup in One Command (Priority: P2)

**Goal**: `scripts/setup-validators.sh` creates three validator keypairs and a trust bundle, skipping files that already exist.

**Independent Test**: Delete `/tmp/alpha.key.json` (if present), run `bash scripts/setup-validators.sh`; all three key files and `/tmp/bundle.cbor` exist. Run again; script exits 0 with "already exists" messages.

- [X] T011 [P] [US2] Create `scripts/setup-validators.sh`: add shebang, `set -euo pipefail`, source `_common.sh`, call `require_cmd decpki`
- [X] T012 [US2] Add per-validator keypair generation loop to `scripts/setup-validators.sh`: for each name in `alpha beta gamma`, check if `${KEY_DIR}/${name}.key.json` exists; if yes print "already exists — skipping"; if no run `decpki keygen --name "$name" --out "${KEY_DIR}/${name}.key.json"` and print the creation log line from `contracts/scripts.md`
- [X] T013 [US2] Add trust bundle generation to `scripts/setup-validators.sh`: run `decpki bundle --validator "${KEY_DIR}/alpha.key.json" --validator "${KEY_DIR}/beta.key.json" --validator "${KEY_DIR}/gamma.key.json" --threshold 2 --grace 24h --out "${BUNDLE_PATH}"` and print the log line; then print the next-step prompt (`Run: scripts/start-demo.sh`)
- [X] T014 [US2] Make `scripts/setup-validators.sh` executable: `chmod +x scripts/setup-validators.sh`

**Checkpoint**: `bash scripts/setup-validators.sh` creates all files on first run; is idempotent on second run.

---

## Phase 5: User Story 3 — Promote an Enrolment in One Command (Priority: P3)

**Goal**: `scripts/promote-enrolment.sh <request-id>` signs, promotes, and regenerates the bundle in one step.

**Independent Test**: With a pending enrolment in `$ENROLMENT_DIR`, run `bash scripts/promote-enrolment.sh <request-id>`; the enrolment JSON status becomes "promoted" and `/tmp/bundle.cbor` is updated.

- [X] T015 [P] [US3] Create `scripts/promote-enrolment.sh`: add shebang, `set -euo pipefail`, source `_common.sh`, call `require_cmd decpki`
- [X] T016 [US3] Add request ID validation to `scripts/promote-enrolment.sh`: read `REQUEST_ID="${1:?Usage: promote-enrolment.sh <request-id>}"`, build `REQUEST_FILE="${ENROLMENT_DIR}/${REQUEST_ID}.json"`, check `-f "$REQUEST_FILE"` and exit 1 with a clear error if absent
- [X] T017 [US3] Add sign-and-promote pipeline to `scripts/promote-enrolment.sh`: run `decpki enrol-sign` for alpha and beta (with log lines), then `decpki enrol-promote --request "$REQUEST_FILE" --validator "${KEY_DIR}/alpha.key.json" --validator "${KEY_DIR}/beta.key.json" --threshold 2` (with log line)
- [X] T018 [US3] Add bundle regeneration to `scripts/promote-enrolment.sh`: run `decpki bundle --validator "${KEY_DIR}/alpha.key.json" --validator "${KEY_DIR}/beta.key.json" --validator "${KEY_DIR}/gamma.key.json" --threshold 2 --grace 24h --out "${BUNDLE_PATH}"` and print the "Done" line from `contracts/scripts.md`
- [X] T019 [US3] Make `scripts/promote-enrolment.sh` executable: `chmod +x scripts/promote-enrolment.sh`

**Checkpoint**: All three quickstart.md scenarios (Scenario 3, 5, 6) pass.

---

## Phase 6: Polish & Cross-Cutting Concerns

- [X] T020 Update `README.md` Quickstart section: replace the current multi-step manual quickstart with a 4-line script-first flow (`pip install -e .` + `pip install -r bff/requirements.txt` + `cd browser && npm install && cd ..` + `bash scripts/setup-validators.sh` + `bash scripts/start-demo.sh`); move the existing manual steps into a `<details><summary>Manual steps</summary>` collapsible block immediately below
- [X] T021 Add `scripts/promote-enrolment.sh <request-id>` call to the README registration flow: after the browser registers a passkey, show the promote script as the next step instead of the three separate CLI commands
- [X] T022 [P] Verify all three scripts pass `bash -n` (syntax check): run `bash -n scripts/start-demo.sh && bash -n scripts/setup-validators.sh && bash -n scripts/promote-enrolment.sh` and confirm exit 0
- [X] T023 [P] Verify all three scripts are executable: run `ls -la scripts/` and confirm all three have `x` bit set

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **US1 (Phase 3)**: Depends on Phase 1 (T001–T002)
- **US2 (Phase 4)**: Depends on Phase 1; independent of US1 — can start in parallel with US1
- **US3 (Phase 5)**: Depends on Phase 1; independent of US1/US2 — can start in parallel
- **Polish (Phase 6)**: Depends on all user stories complete

### Within Each Story

All tasks within a story are sequential (same file).

### Parallel Opportunities

- T011 (US2 start) and T015 (US3 start) can begin in parallel once T001–T002 are done
- T022 and T023 in Polish are independent

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. T001–T002 (Phase 1 setup)
2. T003–T010 (start-demo.sh)
3. **Validate**: run `bash scripts/start-demo.sh`, confirm both servers start, confirm clean Ctrl-C

### Incremental Delivery

- US1 → one-command demo start (highest value, most used)
- US2 → one-command validator setup (prerequisite for US1 in a fresh clone)
- US3 → one-command promote (eliminates last manual step in the register→login flow)
- Polish → README updated, syntax checks pass

---

## Notes

- `_common.sh` is sourced with `source "$(dirname "${BASH_SOURCE[0]}")/_common.sh"` so scripts work from any `$PWD`
- `kill 0` in the trap sends SIGTERM to the entire process group (script + all background children); this is the simplest reliable cross-platform approach
- `lsof` check is best-effort: if `lsof` is absent, skip with a warning rather than failing
- The `--log-level warning` flag can be added to uvicorn to reduce startup noise in the demo
- `decpki enrol-promote` requires `--validator` flags (added in Feature 007 fix) — use both alpha and beta
