# Quickstart: Protected Resource Demo

End-to-end validation. Proves the full loop: register → log in → access protected endpoint → log out.

## Prerequisites

- Feature 004 & 005 complete: a promoted DID in `/tmp/decpki-enrolments/promoted/` and a valid bundle at `/tmp/bundle.cbor`.
- BFF running: `cd bff && SESSION_SECRET=dev-secret-32-bytes-minimum uvicorn main:app --port 8000`
- Demo server running: `cd browser && BUNDLE_PATH=/tmp/bundle.cbor node demo/server.mjs`

---

## Scenario 1: Successful Access to Protected Resource

### Step 1: Log in

Open `http://localhost:3000/login.html`. Enter your registered DID and click **Log In**. Authenticate with biometric/PIN.

**Expected**: Page shows `Logged in as did:local:<uuid>`.

### Step 2: Access the protected endpoint

Click **Call Protected Endpoint**.

**Expected response** (displayed in the UI):

```json
{
  "did": "did:local:<uuid>",
  "issued_at": 1234567890,
  "expires_at": 1234568790,
  "message": "Hello, did:local:<uuid>"
}
```

HTTP 200. The DID in the response matches the logged-in DID.

---

## Scenario 2: Unauthenticated Request Rejected

```bash
curl -v http://localhost:8000/api/me
```

**Expected**: HTTP 401, message: `Missing or invalid Authorization header`.

---

## Scenario 3: Tampered Token Rejected

```bash
curl -H "Authorization: Bearer tampered.token.value" http://localhost:8000/api/me
```

**Expected**: HTTP 401, message indicating the token is invalid.

---

## Scenario 4: Expired Token Rejected

Start the BFF with a 5-second session lifetime:

```bash
SESSION_SECRET=dev-secret-32-bytes-minimum SESSION_LIFETIME_SECONDS=5 uvicorn main:app --port 8000
```

Log in. Wait 6 seconds. Click **Call Protected Endpoint**.

**Expected**: HTTP 401 displayed in the UI with a message indicating the session has expired.

---

## Scenario 5: Button Disabled When Logged Out

Log out (click **Log Out**). Observe the **Call Protected Endpoint** button.

**Expected**: Button is disabled — cannot be clicked while logged out.
