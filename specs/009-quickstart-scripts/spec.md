# Feature Specification: Quickstart Scripts

**Feature Branch**: `009-quickstart-scripts`

**Created**: 2026-06-29

**Status**: Draft

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Start the Full Demo Stack with One Command (Priority: P1)

A developer clones the repository and wants to run the complete demo (BFF + browser server)
without reading multiple README sections or manually juggling terminal windows. A single script
starts everything, prints the URLs, and blocks until stopped.

**Why this priority**: The current quickstart requires the user to coordinate three separate
terminal tabs, remember environment variable names, and know the right directory to `cd` into
first. Every new evaluator hits this friction. A one-command start is the highest-leverage
improvement.

**Independent Test**: Run the start script from the repo root in a fresh shell — within 5 seconds
the browser demo is accessible at `http://localhost:3000/register.html` and the BFF health
endpoint responds at `http://localhost:8000`.

**Acceptance Scenarios**:

1. **Given** a freshly cloned repo with dependencies installed, **When** the user runs
   `./scripts/start-demo.sh`, **Then** both the BFF and browser demo server start, their URLs
   are printed to stdout, and the script keeps running until the user presses Ctrl-C.
2. **Given** the demo is running, **When** the user presses Ctrl-C, **Then** both child
   processes are cleanly terminated with no orphan processes left behind.
3. **Given** `SESSION_SECRET` is not set, **When** the script is run, **Then** the script
   generates a temporary secret automatically and prints a warning that it is not suitable for
   production.
4. **Given** port 8000 or 3000 is already in use, **When** the script is run, **Then** the
   script detects the conflict, prints a clear error message naming the occupied port, and exits
   without starting either server.

---

### User Story 2 — Validator Setup in One Command (Priority: P2)

A developer wants to create the three standard demo validator keypairs and the initial trust
bundle in one step, without remembering the individual `decpki keygen` and `decpki bundle`
commands.

**Why this priority**: Validator setup is a prerequisite for the full demo flow and is the most
common first stumbling block for evaluators who arrive after the quickstart.

**Independent Test**: Run `./scripts/setup-validators.sh` in a clean `/tmp` directory — three
key files and a trust bundle appear within 10 seconds.

**Acceptance Scenarios**:

1. **Given** no validator keys exist, **When** `./scripts/setup-validators.sh` is run,
   **Then** `alpha.key.json`, `beta.key.json`, `gamma.key.json`, and `bundle.cbor` are created
   at configurable paths (defaulting to `/tmp/`).
2. **Given** validator keys already exist at the target paths, **When** the script is run,
   **Then** the script skips regeneration and prints a message indicating the files already exist.
3. **Given** setup succeeds, **When** the script exits, **Then** it prints the next-step
   command to run (the start-demo script).

---

### User Story 3 — Promote an Enrolment in One Command (Priority: P3)

After a user registers in the browser, a developer wants to co-sign and promote the enrolment
with a single script call rather than running three separate CLI commands.

**Why this priority**: The sign → promote pipeline is the second most common friction point after
the initial startup.

**Independent Test**: Run `./scripts/promote-enrolment.sh <request-id>` — the enrolment is
signed by both alpha and beta validators, promoted, and the bundle regenerated, all in under
10 seconds.

**Acceptance Scenarios**:

1. **Given** a pending enrolment request exists, **When** `./scripts/promote-enrolment.sh
   <request-id>` is run, **Then** the request is co-signed by the two default validators,
   promoted to the ledger, and the bundle is regenerated.
2. **Given** the request file does not exist, **When** the script is run, **Then** the script
   prints a clear error and exits non-zero.
3. **Given** the enrolment is already promoted, **When** the script is run, **Then** the script
   prints an appropriate message and exits without error.

---

### Edge Cases

- What if Python or Node.js is not installed? Scripts MUST detect missing runtimes and print
  installation guidance before failing.
- What if the `decpki` CLI is not installed (no `pip install -e .`)? `start-demo.sh` MUST check
  and print the install command.
- What if the scripts are run from a directory other than the repo root? Scripts MUST work
  regardless of the caller's working directory by resolving paths relative to the script's
  own location.
- What if the user is on Windows? Scripts are shell scripts (bash/zsh); Windows support is
  explicitly out of scope for this feature (documented in Assumptions).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The repository MUST contain a `scripts/` directory with at minimum
  `start-demo.sh`, `setup-validators.sh`, and `promote-enrolment.sh`.
- **FR-002**: `start-demo.sh` MUST start both the BFF (port 8000) and the browser demo server
  (port 3000) as child processes and print their URLs on startup.
- **FR-003**: `start-demo.sh` MUST trap SIGINT/SIGTERM and cleanly terminate all child
  processes on exit.
- **FR-004**: `start-demo.sh` MUST auto-generate a `SESSION_SECRET` if none is set, and MUST
  warn the user that it is ephemeral.
- **FR-005**: `start-demo.sh` MUST check that ports 8000 and 3000 are free before starting and
  exit with a descriptive error if either is occupied.
- **FR-006**: `setup-validators.sh` MUST create three validator keypairs and an initial trust
  bundle, skipping files that already exist.
- **FR-007**: `promote-enrolment.sh` MUST accept a request ID as its first positional argument,
  co-sign with the two default validators, promote, and regenerate the bundle.
- **FR-008**: All scripts MUST check for required runtimes (`python3`, `node`) and the `decpki`
  CLI and print actionable error messages if any are missing.
- **FR-009**: All scripts MUST be executable (`chmod +x`) and work when called from any
  directory.
- **FR-010**: The README Quickstart section MUST be updated to reference the new scripts as the
  primary path, with the manual commands retained as a secondary reference.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A developer with dependencies already installed can go from repo root to a running
  demo in under 60 seconds using only the scripts (no README reading required beyond the
  one-line start command).
- **SC-002**: The full register → sign → promote → login flow can be completed using only the
  three scripts — no manual CLI commands needed.
- **SC-003**: Ctrl-C on `start-demo.sh` leaves zero orphan processes (verified with `ps aux`).
- **SC-004**: All scripts exit non-zero and print a human-readable error when a prerequisite is
  missing.

## Assumptions

- Target platform is macOS and Linux (bash/zsh). Windows is explicitly out of scope.
- Dependencies (`python3`, `node`, `pip install -e .`) are already installed before running
  the scripts; the scripts check but do not install them.
- Default validator key paths are `/tmp/alpha.key.json`, `/tmp/beta.key.json`,
  `/tmp/gamma.key.json`; bundle path is `/tmp/bundle.cbor` — all configurable via env vars.
- The existing README manual steps are kept as a secondary reference alongside the scripts.
- `promote-enrolment.sh` uses the two-of-three threshold (alpha + beta) as the default; this
  is sufficient for the demo and matches the existing CLI examples.
