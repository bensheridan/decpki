# Quickstart Validation: Quickstart Scripts

## Prerequisites

- Python 3.11+ and `pip install -e .` completed (so `decpki` CLI is on `$PATH`)
- Node.js 18+ installed
- `bff/requirements.txt` installed: `pip install -r bff/requirements.txt`
- Browser demo deps installed: `cd browser && npm install`

## Scenario 1: Full Demo Stack (US1)

```bash
# From repo root
bash scripts/setup-validators.sh   # one-time: creates keys + bundle
bash scripts/start-demo.sh         # starts BFF + browser server
```

Expected output:
```
[decpki] BFF listening at http://localhost:8000
[decpki] Demo server listening at http://localhost:3000
[decpki] Press Ctrl-C to stop.
```

Open `http://localhost:3000/register.html` in a browser — page loads immediately.
Press Ctrl-C — both servers stop, no orphan processes.

---

## Scenario 2: Validator Setup Idempotency (US2)

```bash
bash scripts/setup-validators.sh   # first run — creates files
bash scripts/setup-validators.sh   # second run — skips existing files, no error
```

Expected on second run: each key file logs "already exists — skipping." Exit code 0.

---

## Scenario 3: Full Register → Promote → Login Flow (US1 + US2 + US3)

```bash
# Terminal 1
bash scripts/start-demo.sh

# Browser: open http://localhost:3000/register.html
# Register a new identity — note the Request ID shown on screen

# Terminal 2
bash scripts/promote-enrolment.sh <request-id>
# Expected:
# [decpki] Signing with alpha validator...
# [decpki] Signing with beta validator...
# [decpki] Promoting enrolment ...
# [decpki] Regenerating trust bundle → /tmp/bundle.cbor
# [decpki] Done. DID is now active. Log in at http://localhost:3000/login.html

# Browser: open http://localhost:3000/login.html — log in with your DID
```

---

## Scenario 4: Port Conflict (US1)

```bash
# Start something on port 8000
python3 -m http.server 8000 &
bash scripts/start-demo.sh
```

Expected: script prints `ERROR: port 8000 is already in use...` and exits 1.

---

## Scenario 5: Missing Dependency (US1)

```bash
# Temporarily rename decpki to simulate missing CLI
PATH="" bash scripts/setup-validators.sh
```

Expected: script prints `ERROR: 'decpki' not found. Run: pip install -e . from the repo root`
and exits 1.

---

## Scenario 6: Custom Key Directory (US2 + US3)

```bash
KEY_DIR=/var/tmp BUNDLE_PATH=/var/tmp/bundle.cbor bash scripts/setup-validators.sh
KEY_DIR=/var/tmp BUNDLE_PATH=/var/tmp/bundle.cbor bash scripts/promote-enrolment.sh <id>
```

Expected: all files created/read from `/var/tmp/` instead of `/tmp/`.

---

## See Also

- [Script interface contracts](contracts/scripts.md)
- [BFF configuration](../../README.md#bff-configuration)
