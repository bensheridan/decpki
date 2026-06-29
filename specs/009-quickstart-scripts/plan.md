# Implementation Plan: Quickstart Scripts

**Branch**: `009-quickstart-scripts` | **Date**: 2026-06-29 | **Spec**: [spec.md](spec.md)

## Summary

Add three bash scripts to a new `scripts/` directory that reduce the demo startup to a single
command each: `setup-validators.sh` (one-time validator + bundle init), `start-demo.sh`
(concurrent BFF + browser server with clean shutdown), and `promote-enrolment.sh <request-id>`
(sign → promote → regenerate bundle pipeline). Update the README Quickstart section to use the
scripts as the primary path.

## Technical Context

**Language/Version**: Bash (compatible with bash 3.2+ / macOS default + Linux)

**Primary Dependencies**: `decpki` CLI (already in repo), `python3`, `node`, `uvicorn`, `lsof`,
`openssl` — all standard on macOS/Linux.

**Storage**: No new storage. Scripts operate on existing files (`*.key.json`, `*.cbor`,
`*.json` enrolment files).

**Testing**: Manual validation against the quickstart.md scenarios. No automated test suite for
shell scripts (out of scope).

**Target Platform**: macOS and Linux. Windows explicitly out of scope.

**Performance Goals**: `start-demo.sh` must have both servers accepting connections within 5
seconds of invocation.

**Constraints**: Zero new dependencies beyond the existing repo stack. Scripts must work from
any `$PWD`.

**Scale/Scope**: Three scripts + README update.

## Constitution Check

| Gate | Status | Notes |
|---|---|---|
| I. Decentralized Trust | PASS | Scripts are operational tooling only |
| II. Offline-First Verification | PASS | No change to verification path |
| III. Cryptographic Auditability | PASS | No change to identity ledger |
| IV. Minimal Credential Surface | PASS | No new credential types |
| V. Explicit Revocation | PASS | Not affected |

No violations.

## Project Structure

### Documentation (this feature)

```text
specs/009-quickstart-scripts/
├── plan.md
├── research.md
├── quickstart.md
├── contracts/
│   └── scripts.md
└── tasks.md
```

### Source Code

```text
scripts/
├── start-demo.sh           ← new (US1)
├── setup-validators.sh     ← new (US2)
└── promote-enrolment.sh    ← new (US3)

README.md                   ← Quickstart section updated (Polish)
```

**Structure Decision**: Single `scripts/` directory at repo root, matching the pattern of the
existing `demo.sh`. No subdirectories needed.

## Implementation Notes

### `scripts/setup-validators.sh`

```bash
#!/usr/bin/env bash
set -euo pipefail
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
KEY_DIR="${KEY_DIR:-/tmp}"
BUNDLE_PATH="${BUNDLE_PATH:-/tmp/bundle.cbor}"

require_cmd() { command -v "$1" &>/dev/null || { echo "ERROR: '$1' not found. $2"; exit 1; }; }
require_cmd decpki "Run: pip install -e . from the repo root"

for name in alpha beta gamma; do
    out="${KEY_DIR}/${name}.key.json"
    if [[ -f "$out" ]]; then
        echo "[decpki] ${out} already exists — skipping."
    else
        echo "[decpki] Generating ${name} validator keypair → ${out}"
        decpki keygen --name "$name" --out "$out"
    fi
done

echo "[decpki] Generating trust bundle → ${BUNDLE_PATH}"
decpki bundle \
  --validator "${KEY_DIR}/alpha.key.json" \
  --validator "${KEY_DIR}/beta.key.json" \
  --validator "${KEY_DIR}/gamma.key.json" \
  --threshold 2 --grace 24h --out "${BUNDLE_PATH}"

echo "[decpki] Setup complete. Run: scripts/start-demo.sh"
```

### `scripts/start-demo.sh`

Key patterns:
- `trap 'kill 0' EXIT INT TERM` — kills the entire process group on any exit
- Port check with `lsof -i :PORT -sTCP:LISTEN -t`
- `SESSION_SECRET` auto-generation with `openssl rand -hex 32`
- Launch BFF with `uvicorn bff.main:app --port $BFF_PORT`
- Launch browser server with `node browser/demo/server.mjs`
- `wait` blocks until both children exit

### `scripts/promote-enrolment.sh`

```bash
REQUEST_ID="${1:?Usage: promote-enrolment.sh <request-id>}"
REQUEST_FILE="${ENROLMENT_DIR}/${REQUEST_ID}.json"
[[ -f "$REQUEST_FILE" ]] || { echo "ERROR: $REQUEST_FILE not found"; exit 1; }

decpki enrol-sign --request "$REQUEST_FILE" --validator "${KEY_DIR}/alpha.key.json"
decpki enrol-sign --request "$REQUEST_FILE" --validator "${KEY_DIR}/beta.key.json"
decpki enrol-promote --request "$REQUEST_FILE" \
  --validator "${KEY_DIR}/alpha.key.json" \
  --validator "${KEY_DIR}/beta.key.json" \
  --threshold 2

decpki bundle \
  --validator "${KEY_DIR}/alpha.key.json" \
  --validator "${KEY_DIR}/beta.key.json" \
  --validator "${KEY_DIR}/gamma.key.json" \
  --threshold 2 --grace 24h --out "${BUNDLE_PATH}"
```

### `decpki keygen` interface

Need to verify the `keygen` CLI accepts `--out` flag for custom output path. If not, scripts
write to a default location and copy. Check during implementation.

### README Quickstart update

Replace the multi-step manual quickstart with:
```markdown
## Quickstart

```bash
pip install -e . && pip install -r bff/requirements.txt
cd browser && npm install && cd ..
bash scripts/setup-validators.sh   # one-time: generates validator keys + trust bundle
bash scripts/start-demo.sh         # starts BFF (port 8000) + demo server (port 3000)
```
Open http://localhost:3000/register.html
```

Keep the existing manual steps in a collapsible `<details>` block or as a "Manual steps" subsection.
