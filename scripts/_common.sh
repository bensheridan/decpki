# _common.sh — shared helpers for decpki quickstart scripts
# Usage: source "$(dirname "${BASH_SOURCE[0]}")/_common.sh"

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Configurable defaults (override via environment variables)
KEY_DIR="${KEY_DIR:-/tmp}"
BUNDLE_PATH="${BUNDLE_PATH:-/tmp/bundle.cbor}"
ENROLMENT_DIR="${ENROLMENT_DIR:-/tmp/decpki-enrolments}"
BFF_PORT="${BFF_PORT:-8000}"
DEMO_PORT="${DEMO_PORT:-3000}"
BFF_STORE_PATH="${BFF_STORE_PATH:-/tmp/decpki-bff.db}"

log() {
    echo "[decpki] $*"
}

require_cmd() {
    local cmd="$1"
    local hint="${2:-Install ${cmd}}"
    if ! command -v "$cmd" &>/dev/null; then
        echo "ERROR: '${cmd}' not found. ${hint}" >&2
        exit 1
    fi
}
