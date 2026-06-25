# Quickstart: BFF Session Issuance

End-to-end validation guide. Proves the login pipeline works from WebAuthn assertion through trust bundle verification to session token issuance and protected resource access.

## Prerequisites

- Feature 004 complete: a promoted DID exists in `/tmp/decpki-enrolments/promoted/` and a valid bundle exists at `/tmp/bundle.cbor`.
- BFF running: `cd bff && SESSION_SECRET=dev-secret-32-bytes-minimum uvicorn main:app --port 8000`
- Demo server running: `cd browser && BUNDLE_PATH=/tmp/bundle.cbor node demo/server.mjs`
- Known DID from registration (shown in `register.html` after Feature 004 enrolment).

---

## Scenario 1: Successful Login

### Step 1: Open the login demo

Open `http://localhost:3000/login.html` in a browser that has the registered passkey.

### Step 2: Log in

Enter the DID from Feature 004 registration and click **Log In**. Your device will prompt for biometric/PIN.

**Expected outcome**:
- Page shows: `Logged in as did:local:<uuid4>`
- Session token and expiry displayed.
- DevTools → Application → Local Storage → `decpki_session`, `decpki_refresh`, `decpki_did` all populated.

### Step 3: Access a protected resource

Click **Call Protected Endpoint**. The demo sends `GET /login/verify` with `Authorization: Bearer <token>`.

**Expected outcome**:
- Response: `{ "did": "did:local:<uuid4>", "expires_at": ... }` — HTTP 200.

---

## Scenario 2: Revoked DID Rejected at Login

### Setup: revoke the DID and regenerate the bundle

```bash
decpki enrol-revoke \
  --did did:local:<uuid4> \
  --validator /tmp/alpha.key.json \
  --validator /tmp/beta.key.json \
  --threshold 2

decpki bundle \
  --validator /tmp/alpha.key.json \
  --validator /tmp/beta.key.json \
  --validator /tmp/gamma.key.json \
  --threshold 2 --grace 24h --out /tmp/bundle.cbor
```

Wait up to `BUNDLE_REFRESH_INTERVAL` seconds (default 300s; set `BUNDLE_REFRESH_INTERVAL=5` for testing) for the BFF to reload the bundle.

### Attempt login

**Expected outcome**: HTTP 401, message: `DID not active in trust bundle`.

---

## Scenario 3: Expired Session Token Rejected

Use `SESSION_LIFETIME_SECONDS=5` when starting the BFF:

```bash
SESSION_SECRET=dev-secret-32-bytes-minimum SESSION_LIFETIME_SECONDS=5 uvicorn main:app --port 8000
```

Log in. Wait 6 seconds. Call `GET /login/verify`:

**Expected outcome**: HTTP 401, `Token expired`.

---

## Scenario 4: Silent Token Refresh

Use a short session lifetime:

```bash
SESSION_SECRET=dev-secret-32-bytes-minimum SESSION_LIFETIME_SECONDS=130 uvicorn main:app --port 8000
```

Log in. Wait ~2 minutes (the browser schedules refresh at `exp - 120s`). Check the network panel.

**Expected outcome**: A `POST /login/refresh` request fires automatically, a new `decpki_session` value appears in localStorage, and no biometric prompt was shown.

---

## Scenario 5: Logout Invalidates Refresh Token

1. Log in (Scenario 1).
2. Note the refresh token from localStorage.
3. Click **Log Out**.
4. Manually call `POST /login/refresh` with the noted refresh token:

```bash
curl -X POST http://localhost:8000/login/refresh \
  -H "Content-Type: application/json" \
  -d '{"refresh_token":"<noted-token>"}'
```

**Expected outcome**: HTTP 401, `Refresh token not found or expired`.

---

## Scenario 6: Expired Challenge Rejected (Replay Prevention)

Use `curl` to call `POST /login/start`, wait 61 seconds, then submit a fake completion using the returned challenge:

```bash
RESP=$(curl -s -X POST http://localhost:8000/login/start \
  -H "Content-Type: application/json" \
  -d '{"did":"did:local:<uuid4>"}')
CHALLENGE=$(echo $RESP | python3 -c "import sys,json; print(json.load(sys.stdin)['challenge'])")
sleep 61
curl -X POST http://localhost:8000/login/complete \
  -H "Content-Type: application/json" \
  -d "{\"did\":\"did:local:<uuid4>\",\"assertion\":{\"response\":{\"clientDataJSON\":\"$(echo -n "{\"type\":\"webauthn.get\",\"challenge\":\"$CHALLENGE\"}" | base64)\",\"authenticatorData\":\"\",\"signature\":\"\"}}}"
```

**Expected outcome**: HTTP 401, `Challenge expired or not found`.
