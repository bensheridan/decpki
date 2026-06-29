# Research: Quickstart Scripts

## Shell Compatibility

**Decision**: Bash (`#!/usr/bin/env bash`) with `set -euo pipefail`.

**Rationale**: The existing `demo.sh` uses bash. macOS ships bash 3.2; all patterns used here
(process groups, `trap`, `lsof`, `$BASHPID`) work on bash 3.2+. `#!/usr/bin/env bash` finds
the user's preferred bash installation (e.g. brew-installed bash 5).

**Alternatives considered**:
- `#!/bin/sh` (POSIX) — no process groups or `wait -n`; harder to manage multiple child PIDs cleanly.
- zsh — not universally available on Linux.

---

## Child Process Management / Clean Shutdown

**Decision**: Launch child processes in a background process group; `trap` SIGINT/SIGTERM to
`kill -- -$CHILD_PID` (kill the whole group).

Pattern:
```bash
trap 'kill 0' EXIT INT TERM   # kill entire process group on exit
uvicorn ... &
node ... &
wait
```

`kill 0` sends SIGTERM to every process in the current process group (the script + all its
background children). This is the simplest reliable cross-platform approach.

**Alternatives considered**:
- Tracking individual PIDs — works but fragile if a child spawns sub-children.
- `pkill -P $$` — not available on all BSD/macOS versions.

---

## Port Conflict Detection

**Decision**: Use `lsof -i :<port>` before starting servers.

```bash
if lsof -i :8000 -sTCP:LISTEN -t &>/dev/null; then
    echo "ERROR: port 8000 is already in use"; exit 1
fi
```

`lsof` is available on macOS and most Linux distros. Falls back gracefully if not installed
(skip the check with a warning).

---

## SESSION_SECRET Auto-Generation

**Decision**: Generate a 32-byte hex secret with `openssl rand -hex 32` if `SESSION_SECRET`
is unset. Print a prominent warning that the secret is ephemeral.

**Rationale**: `openssl` is available on macOS and Linux by default. The alternative
(`python3 -c "import secrets; ..."`) adds a dependency on Python being importable before
uvicorn is started, which is already guaranteed but adds complexity.

---

## Path Resolution (Script Self-Location)

**Decision**: All scripts resolve their own directory with:
```bash
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
```

This is the same pattern used in `demo.sh` and works regardless of the caller's `$PWD`.

---

## Configurable Paths via Environment Variables

| Variable | Default | Used by |
|---|---|---|
| `KEY_DIR` | `/tmp` | `setup-validators.sh`, `promote-enrolment.sh` |
| `BUNDLE_PATH` | `/tmp/bundle.cbor` | all three scripts |
| `ENROLMENT_DIR` | `/tmp/decpki-enrolments` | `promote-enrolment.sh` |
| `BFF_PORT` | `8000` | `start-demo.sh` |
| `DEMO_PORT` | `3000` | `start-demo.sh` |
| `SESSION_SECRET` | *(auto-generated)* | `start-demo.sh` |
| `BFF_STORE_PATH` | `/tmp/decpki-bff.db` | `start-demo.sh` |

---

## Prerequisite Checking Pattern

```bash
require_cmd() {
    command -v "$1" &>/dev/null || { echo "ERROR: '$1' not found. $2"; exit 1; }
}
require_cmd python3  "Install Python 3.11+ from https://python.org"
require_cmd node     "Install Node.js 18+ from https://nodejs.org"
require_cmd decpki   "Run: pip install -e . from the repo root"
```

---

## Constitution Gate

These are shell scripts in the repository root. They do not affect the PKI trust path,
cryptographic primitives, or bundle format. No constitution gates apply.
