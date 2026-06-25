# Quickstart: FIDO2 Registration & Chain Enrolment

End-to-end validation guide. Proves the enrolment pipeline works from browser credential creation through validator co-signing to trust bundle inclusion and offline verification.

## Prerequisites

- Python 3.11+ with `decpki` CLI installed (from repo root: `pip install -e .`)
- Node.js 20+ and the `browser/` library built (`cd browser && npm install && npm run build`)
- Three validator keypairs generated (reuse from Feature 003 demo, or regenerate):

```bash
decpki keygen --name alpha --out /tmp/alpha.key.json
decpki keygen --name beta  --out /tmp/beta.key.json
decpki keygen --name gamma --out /tmp/gamma.key.json
```

## Scenario 1: New User Registration

### Step 1: Start the BFF

```bash
cd bff
pip install -r requirements.txt
VALIDATOR_ALPHA=/tmp/alpha.key.json \
VALIDATOR_BETA=/tmp/beta.key.json \
VALIDATOR_GAMMA=/tmp/gamma.key.json \
THRESHOLD=2 \
uvicorn main:app --port 8000
# → http://localhost:8000
```

### Step 2: Open the registration demo

Build the browser demo and start its server in a separate terminal:

```bash
cd browser
BUNDLE_PATH=/tmp/bundle.cbor node demo/server.mjs
# → http://localhost:3000
```

Open `http://localhost:3000/register.html` in Chrome/Firefox/Safari.

### Step 3: Register a credential

Click **Register**. Your browser will prompt for biometric confirmation (Touch ID, Windows Hello, security key, etc.). After confirming:

**Expected outcome**:
- The page shows a `request_id` (UUID4) and `did:local:<uuid4>`.
- Status is `pending` with 0 of 2 signatures collected.

### Step 4: Validator co-signing (terminal)

Each validator signs the pending request:

```bash
# Validator alpha signs
decpki enrol-sign \
  --request /tmp/decpki-enrolments/<request-id>.json \
  --validator /tmp/alpha.key.json

# Validator beta signs
decpki enrol-sign \
  --request /tmp/decpki-enrolments/<request-id>.json \
  --validator /tmp/beta.key.json
```

**Expected output after second signing**:
```
Signatures: 2/2 — quorum reached. Ready to promote.
```

### Step 5: Promote to ledger

```bash
decpki enrol-promote \
  --request /tmp/decpki-enrolments/<request-id>.json \
  --threshold 2
```

**Expected output**:
```
Promoted: did:local:<uuid4>
Identity written to ledger.
```

### Step 6: Generate bundle and verify

```bash
decpki bundle \
  --validator /tmp/alpha.key.json \
  --validator /tmp/beta.key.json \
  --validator /tmp/gamma.key.json \
  --threshold 2 \
  --grace 24h \
  --out /tmp/bundle.cbor
```

In the browser demo at `http://localhost:3000`:
1. Click **Sync Bundle**
2. Enter the DID shown after Step 3
3. Click **Verify** → Result: `VALID`
4. Enable Offline mode in DevTools → Click **Verify** again → Still `VALID`

---

## Scenario 2: Add Credential (Multi-Device)

### Prerequisites: a promoted DID from Scenario 1

### Steps

1. Open `http://localhost:3000/register.html` on a **second device or browser profile**.
2. Click **Add Credential to Existing DID** and enter the DID from Scenario 1.
3. The browser will first ask you to authenticate with an existing credential (ownership proof), then create a new credential.
4. Follow Steps 4–6 from Scenario 1 with the new `request_id`.

**Expected outcome**: Both credentials verify as `VALID` for the same DID.

---

## Scenario 3: Rejection of Non-Ed25519 Credential

This verifies the algorithm enforcement (FR-004 + constitution Principle IV).

Simulate a P-256 submission:

```bash
curl -X POST http://localhost:8000/enrolment/submit \
  -H "Content-Type: application/json" \
  -d '{"pending_did":"did:local:test","credential":{"response":{"attestationObject":"<p256-cose-key-base64>"}}}'
```

**Expected**: HTTP 422, body: `{"detail": "Only ed25519 credentials (COSE alg -8) are accepted."}`

---

## Scenario 4: Expired Request Not Promoted

Set a very short TTL to verify expiry behaviour:

```bash
ENROLMENT_TTL_SECONDS=5 uvicorn main:app --port 8000
```

Submit a credential. Wait 6 seconds. Attempt to sign it:

```bash
decpki enrol-sign --request /tmp/decpki-enrolments/<id>.json --validator /tmp/alpha.key.json
```

**Expected**: Error: `Request <id> has expired and cannot be signed.`

---

## Scenario 5: Duplicate Credential Rejected

Register the same device twice. On the second submission to `POST /enrolment/submit`:

**Expected**: HTTP 409, body: `{"detail": "Credential ID already registered."}`
