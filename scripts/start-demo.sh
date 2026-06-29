#!/usr/bin/env bash
set -euo pipefail
# shellcheck source=_common.sh
source "$(dirname "${BASH_SOURCE[0]}")/_common.sh"

# Parse flags
while [[ $# -gt 0 ]]; do
    case "$1" in
        --bff-port)  BFF_PORT="$2";  shift 2 ;;
        --demo-port) DEMO_PORT="$2"; shift 2 ;;
        *) echo "Unknown flag: $1" >&2; exit 1 ;;
    esac
done

# Prerequisite checks
require_cmd python3   "Install Python 3.11+ from https://python.org"
require_cmd node      "Install Node.js 18+ from https://nodejs.org"
require_cmd uvicorn   "Run: pip install -r bff/requirements.txt"
require_cmd decpki    "Run: pip install -e . from the repo root"

# Port conflict detection
check_port() {
    local port="$1"
    local name="$2"
    if command -v lsof &>/dev/null; then
        if lsof -i :"$port" -sTCP:LISTEN -t &>/dev/null; then
            echo "ERROR: port ${port} is already in use. Stop the existing process or set ${name}=<other>." >&2
            exit 1
        fi
    else
        echo "WARNING: lsof not found; skipping port ${port} conflict check." >&2
    fi
}
check_port "$BFF_PORT"  "BFF_PORT"
check_port "$DEMO_PORT" "DEMO_PORT"

# SESSION_SECRET auto-generation
if [[ -z "${SESSION_SECRET:-}" ]]; then
    SESSION_SECRET="$(openssl rand -hex 32)"
    export SESSION_SECRET
    echo "WARNING: SESSION_SECRET not set — generated ephemeral key. Not suitable for production." >&2
fi

# Clean shutdown of entire process group on exit
trap 'kill 0' EXIT INT TERM

# Launch BFF (refresh bundle every 5s so promote-enrolment.sh takes effect immediately)
(
    cd "$REPO_ROOT/bff"
    SESSION_SECRET="$SESSION_SECRET" \
    BFF_STORE_PATH="${BFF_STORE_PATH}" \
    BUNDLE_PATH="${BUNDLE_PATH}" \
    BUNDLE_REFRESH_INTERVAL="${BUNDLE_REFRESH_INTERVAL:-5}" \
    uvicorn main:app --port "$BFF_PORT" --log-level warning
) &

# Launch browser demo server
BUNDLE_PATH="${BUNDLE_PATH}" \
PORT="$DEMO_PORT" \
BFF_PORT="$BFF_PORT" \
node "$REPO_ROOT/browser/demo/server.mjs" &

log "BFF listening at http://localhost:${BFF_PORT}"
log "Demo server listening at http://localhost:${DEMO_PORT}"
log "Press Ctrl-C to stop."

wait
