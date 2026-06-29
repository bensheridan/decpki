# Quickstart: BFF Persistent Storage Validation

## Prerequisites

- BFF dependencies installed (`pip install -r bff/requirements.txt`)
- A promoted enrolment on disk (`/tmp/decpki-enrolments/promoted/*.json`)
- `SESSION_SECRET` env var set

## Scenario 1: Session Survives Restart

```bash
# Start BFF (store will be created at /tmp/decpki-bff.db)
cd bff && uvicorn main:app --port 8000

# In another terminal — log in and capture the refresh token
RT=$(curl -s -X POST http://localhost:8000/login/complete \
  -H 'Content-Type: application/json' \
  -d '{"did":"<your-did>","assertion":{...}}' | jq -r .refresh_token)

# Refresh to get a session token
ST=$(curl -s -X POST http://localhost:8000/login/refresh \
  -H 'Content-Type: application/json' \
  -d "{\"refresh_token\":\"$RT\"}" | jq -r .session_token)

# Hit a protected endpoint — expect 200
curl -s http://localhost:8000/api/me -H "Authorization: Bearer $ST"

# Kill and restart the BFF (Ctrl-C, then re-run uvicorn)
# No state lost — the .db file persists.

# After restart — refresh again to get a fresh session token
ST2=$(curl -s -X POST http://localhost:8000/login/refresh \
  -H 'Content-Type: application/json' \
  -d "{\"refresh_token\":\"$RT\"}" | jq -r .session_token)

# Expected: 200 with DID — no re-login required
curl -s http://localhost:8000/api/me -H "Authorization: Bearer $ST2"
```

**Expected outcome**: `/api/me` returns 200 both before and after the restart.

---

## Scenario 2: Revocation Survives Restart

```bash
# After logging in (same $RT / $ST from Scenario 1):

# List sessions and capture session_id
SID=$(curl -s -X POST http://localhost:8000/api/sessions \
  -H "Authorization: Bearer $ST" \
  -H 'Content-Type: application/json' \
  -d "{\"refresh_token\":\"$RT\"}" | jq -r '.sessions[0].session_id')

# Revoke the session
curl -s -X DELETE http://localhost:8000/api/sessions/$SID \
  -H "Authorization: Bearer $ST"

# Restart BFF (Ctrl-C, re-run uvicorn)

# After restart, old token should be rejected
curl -s http://localhost:8000/api/me -H "Authorization: Bearer $ST"
# Expected: 401 {"detail":"Session has been revoked"}
```

---

## Scenario 3: Custom Store Path

```bash
BFF_STORE_PATH=/var/data/my-demo.db uvicorn main:app --port 8000
```

Store is created at the configured path. Default is `/tmp/decpki-bff.db`.

---

## Running the Test Suite

```bash
cd bff && python -m pytest tests/ -v
```

All existing session tests pass against the SQLite backend (in-memory mode).
Integration tests check cross-restart persistence using a temp file.

---

## See Also

- [Data model](data-model.md) — SQLite schema details
- [SessionStore contract](contracts/session-store.md) — interface preserved by the new impl
