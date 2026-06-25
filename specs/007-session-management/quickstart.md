# Quickstart: Session Management

End-to-end validation guide. Proves session listing, revocation, and multi-device enrolment.

## Prerequisites

- Features 004–006 complete: a promoted DID, valid bundle at `/tmp/bundle.cbor`.
- BFF running: `cd bff && SESSION_SECRET=dev-secret-32-bytes-minimum uvicorn main:app --port 8000`
- Demo server: `cd browser && BUNDLE_PATH=/tmp/bundle.cbor node demo/server.mjs`

---

## Scenario 1: View Active Sessions

1. Log in at `http://localhost:3000/login.html`.
2. Navigate to `http://localhost:3000/sessions.html`.

**Expected**: A list showing at least one session. The current session is marked **This device**.

---

## Scenario 2: Two Sessions Visible After Second Login

1. Log in from tab A. Open `sessions.html` — see 1 session.
2. Open tab B, log in with the same DID at `login.html`.
3. Return to tab A, refresh `sessions.html`.

**Expected**: Two sessions listed. Tab A's session is marked **This device**; tab B's is not.

---

## Scenario 3: Revoke Another Session

Continuing from Scenario 2:

1. In tab A, click **Revoke** on the session that is NOT **This device** (tab B's session).

**Expected**:
- Tab A: session list updates to show only 1 session.
- Tab B: click **Call Protected Endpoint** → HTTP 401. Tab B is effectively logged out.

---

## Scenario 4: Revoke Current Session (Self-Revocation)

1. Log in and open `sessions.html`.
2. Click **Revoke** on the **This device** session.

**Expected**: The page shows a logged-out state immediately. The session token is rejected by all protected endpoints.

---

## Scenario 5: Add New Device

1. Log in and open `sessions.html`.
2. Click **Add New Device**.
3. Complete the biometric/PIN prompt on the current device (or a second device if available).

**Expected**:
- A confirmation is shown: `Enrolment request created: <request-id>`.
- `GET http://localhost:8000/enrolment/` lists a new pending request for the same DID.

After validator co-signing and promotion:
```bash
decpki enrol-sign --request /tmp/decpki-enrolments/<request-id>.json --validator /tmp/alpha.key.json
decpki enrol-sign --request /tmp/decpki-enrolments/<request-id>.json --validator /tmp/beta.key.json
decpki enrol-promote --request /tmp/decpki-enrolments/<request-id>.json --threshold 2
decpki bundle --validator /tmp/alpha.key.json --validator /tmp/beta.key.json --validator /tmp/gamma.key.json --threshold 2 --grace 24h --out /tmp/bundle.cbor
```

Logging in from the new device now succeeds.

---

## Scenario 6: Unauthenticated Access Rejected

```bash
curl http://localhost:8000/api/sessions -H "Content-Type: application/json" -d '{"refresh_token":"fake"}'
```

**Expected**: HTTP 401 — `Missing or invalid Authorization header`.

---

## Scenario 7: Revoke Non-Existent Session

```bash
curl -X DELETE http://localhost:8000/api/sessions/0000000000000000 \
  -H "Authorization: Bearer <valid-token>"
```

**Expected**: HTTP 404 — `Session not found`.
