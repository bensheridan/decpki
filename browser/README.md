# decpki-client

Browser offline identity client for the decentralised PKI prototype.

Verifies W3C DID identities against a locally-stored trust bundle with **zero network calls** during verification. A Service Worker handles background bundle sync.

## Browser support

| Browser | Min version | Ed25519 |
|---------|-------------|---------|
| Chrome  | 113+        | native  |
| Firefox | 129+        | native  |
| Safari  | 17+         | native  |
| Older   | —           | @noble/ed25519 fallback |

## Quickstart

```html
<!-- 1. Copy dist/decpki-sw.js to your web root -->
<!-- 2. Load the IIFE bundle -->
<script src="/decpki-client.iife.js"></script>
<script>
  const client = new DecPKILib.DecPKIClient({
    bundleEndpoint: 'https://your-server.example/bundle.cbor',
    swPath: '/decpki-sw.js',
  });

  // Init once per page load
  await client.init();

  // Verify a DID — works offline once a bundle is synced
  const result = await client.verify('did:local:payments-svc');
  // result.outcome: 'VALID' | 'NOT_FOUND' | 'EXPIRED' | 'TAMPERED' | 'QUORUM_FAILURE' | 'NO_BUNDLE'
  console.log(result.outcome, result.message);

  // Listen for auto-sync updates
  client.onBundleUpdated = ({ expiresAt }) => {
    console.log('Fresh bundle synced, expires', new Date(expiresAt * 1000));
  };
</script>
```

## ESM import

```js
import { DecPKIClient } from './decpki-client.mjs';

const client = new DecPKIClient({ bundleEndpoint: '/bundle.cbor' });
await client.init();
const result = await client.verify('did:local:api-gateway');
```

## API reference

See [`src/index.d.ts`](src/index.d.ts) for full TypeScript types.

| Method | Returns | Description |
|--------|---------|-------------|
| `new DecPKIClient(config)` | `DecPKIClient` | Create client; `config.bundleEndpoint` required |
| `client.init()` | `Promise<void>` | Register SW, open IndexedDB, load bundle |
| `client.verify(did)` | `Promise<VerificationResult>` | Verify DID offline; < 500ms |
| `client.getSyncState()` | `Promise<BundleSyncState\|null>` | Current sync status |
| `client.requestSync()` | `Promise<void>` | Ask SW for immediate sync |
| `client.destroy()` | `void` | Clean up listeners |

## Outcomes

| `outcome` | Meaning |
|-----------|---------|
| `VALID` | DID found, all proofs pass, bundle not expired |
| `NOT_FOUND` | DID not in bundle |
| `EXPIRED` | Bundle has passed `expiresAt` |
| `TAMPERED` | Merkle proof failed (bundle integrity issue) |
| `QUORUM_FAILURE` | Bundle has fewer valid signatures than threshold |
| `NO_BUNDLE` | No bundle stored; sync first |
| `UNSUPPORTED` | Browser lacks required crypto APIs |

## Security model

**What the client guarantees**:
- Any modification to the bundle (identity records, proofs, expiry, validator set) is detected — ed25519 signatures cover the full canonical payload.
- A MITM who intercepts the bundle fetch cannot forge a replacement bundle without the validators' private keys. The worst they can do is block fetches or serve an old-but-valid bundle.
- The `bundleEndpoint` must use HTTPS (localhost is the only plain-HTTP exception). The constructor throws if this is violated.
- Signature quorum is fail-closed: if the stored bundle has no recorded valid-signature count, `verify()` returns `QUORUM_FAILURE` rather than proceeding.

**Revocation and the BFF boundary**:

In a typical deployment the browser talks to a Backend-for-Frontend (BFF), not directly to external services. The BFF is always online and should perform its own server-side verification (using the Python `decpki` library) on every request that matters. If an identity has been revoked, the BFF rejects the request — the browser's cached bundle state is irrelevant to enforcement.

Browser-side verification serves a different purpose: **UX awareness when the BFF is unreachable** (airplane mode, field work, loss of connectivity). It lets the UI show the user their identity status without a round-trip, but it is not the security boundary.

```
Browser ←── verify() ──→ cached bundle   (UX, offline awareness)
Browser ←──────────────→ BFF             (enforcement, always fresh)
BFF     ←──────────────→ PKI server      (server-side verify, short-lived cache)
```

The revocation lag (max = bundle validity period) only applies in the genuine offline case — when the BFF itself is unreachable. For most applications this is an acceptable edge case; the BFF remains the authoritative enforcement point.

## Registration (FIDO2 / Passkeys)

The `DecPKIRegistration` class (`src/registration.js`) lets users create a FIDO2 passkey and submit it for chain enrolment via a BFF.

```js
import { DecPKIRegistration } from './registration.js';

const reg = new DecPKIRegistration({
  bffBaseUrl: 'https://your-bff.example/enrolment',  // HTTPS required (localhost excepted)
});

// Register a new identity (browser prompts for biometric/PIN)
const result = await reg.register();
// result: { requestId, did, status: 'pending', threshold, signaturesCollected, expiresAt }

// After validators co-sign via CLI, the identity enters the next bundle
// and DecPKIClient.verify(result.did) returns 'VALID'

// Add a second credential to an existing DID (proves ownership of existing credential first)
const result2 = await reg.addCredential('did:local:<uuid>');

// Poll enrolment request status
const status = await reg.getStatus(result.requestId);
```

**BFF requirement**: Registration requires a running BFF (see `bff/` directory in the repo root). The BFF handles challenge issuance, COSE key extraction, and enrolment request creation. Start it with:

```bash
cd bff
pip install -r requirements.txt
uvicorn main:app --port 8000
```

**Validator co-signing** (after user registers):

```bash
decpki enrol-sign --request /tmp/decpki-enrolments/<request-id>.json --validator /tmp/alpha.key.json
decpki enrol-sign --request /tmp/decpki-enrolments/<request-id>.json --validator /tmp/beta.key.json
decpki enrol-promote --request /tmp/decpki-enrolments/<request-id>.json --threshold 2
decpki bundle --validator /tmp/alpha.key.json --validator /tmp/beta.key.json --validator /tmp/gamma.key.json --threshold 2 --grace 24h --out /tmp/bundle.cbor
```

**Registration demo**: open `http://localhost:3000/register.html` while the demo server and BFF are both running.

## Session / Login (FIDO2 Authentication)

The `DecPKISession` class (`src/session.js`) handles WebAuthn login against the BFF, JWT session token storage, silent refresh, and logout.

```js
import { DecPKISession } from './session.js';

const session = new DecPKISession({
  bffBaseUrl: 'http://localhost:8000/login',  // HTTPS required (localhost excepted)
});

// Log in — browser prompts for biometric/PIN, BFF verifies against trust bundle
const result = await session.login('did:local:<uuid>');
// result: { did, sessionToken, refreshToken, expiresAt, refreshExpiresAt }

// Retrieve token for use in API calls (silently refreshes if expiry < 120s away)
const token = await session.getToken();
// Use as: Authorization: Bearer <token>

// Check login state
if (session.isLoggedIn()) {
  const did = session.getDid();
}

// Explicit logout — invalidates refresh token server-side
await session.logout();
```

**Error classes**:

| Class | Thrown when |
|-------|-------------|
| `LoginCancelledError` | User dismissed the WebAuthn biometric/PIN prompt |
| `LoginFailedError` | BFF rejected the assertion (bad signature, expired challenge, revoked DID) |
| `DIDNotFoundError` | DID not found in promoted enrolments at `/login/start` |
| `SessionExpiredError` | Refresh token expired — user must call `login()` again |

**BFF requirement**: The BFF (`bff/`) must be running with a `SESSION_SECRET` env var:

```bash
cd bff
SESSION_SECRET=your-secret-min-32-chars uvicorn main:app --port 8000
```

**Login demo**: open `http://localhost:3000/login.html` with the demo server and BFF running. Register first via `/register.html` to get a promoted DID, then log in.

**Full validation scenarios**: see [`../specs/005-bff-session-issuance/quickstart.md`](../specs/005-bff-session-issuance/quickstart.md).

**Protected resource**: once logged in, use `getToken()` to call `GET /api/me` on the BFF — the standard pattern for accessing any protected endpoint:

```js
const token = await session.getToken();
const r = await fetch('http://localhost:8000/api/me', {
  headers: { 'Authorization': `Bearer ${token}` },
});
const me = await r.json();
// { did, issued_at, expires_at, message }
```

The login demo at `/login.html` does exactly this when you click **Call Protected Endpoint**.

## Bundle sync

The Service Worker automatically syncs when:
- The SW activates (page load / restart)
- The device comes online (`window` online event)
- The bundle has consumed > 80% of its validity window

Multiple tabs share a single sync; duplicates are suppressed.

## Running the demo

The demo requires a real browser tab (not a preview panel) — Service Workers need an HTTP origin.

**Step 1: Generate a test bundle** (from the repo root)

```bash
decpki keygen --name alpha --out /tmp/alpha.key.json
decpki keygen --name beta  --out /tmp/beta.key.json
decpki keygen --name gamma --out /tmp/gamma.key.json

PUBKEY=$(python3 -c "import json; d=json.load(open('/tmp/alpha.key.json')); print(d['public_key'])")

decpki register \
  --did did:local:test-svc \
  --pubkey "$PUBKEY" \
  --validator /tmp/alpha.key.json \
  --validator /tmp/beta.key.json

decpki bundle \
  --validator /tmp/alpha.key.json \
  --validator /tmp/beta.key.json \
  --validator /tmp/gamma.key.json \
  --threshold 2 \
  --grace 24h \
  --out /tmp/bundle.cbor
```

**Step 2: Build the JS library**

```bash
cd browser
npm install
npm run build
```

**Step 3: Start the dev server**

```bash
cd browser
BUNDLE_PATH=/tmp/bundle.cbor node demo/server.mjs
# → http://localhost:3000
```

Open **http://localhost:3000** in your browser. Then:

1. Click **Sync Bundle** — fetches `bundle.cbor` via the Service Worker
2. Type `did:local:test-svc` in the input and click **Verify** — shows `VALID`
3. Open DevTools → Network → set throttle to **Offline**
4. Click **Verify** again — still `VALID` with zero network requests

To test expiry: use `--grace 30s` in the bundle command, sync, wait 31 seconds, verify — shows `EXPIRED`.

## Build

```bash
npm install
npm run build   # → dist/decpki-client.mjs, dist/decpki-client.iife.js, dist/decpki-sw.js
npm test        # unit tests (Vitest + happy-dom)
```

## Validation

See [`../specs/003-browser-offline-client/quickstart.md`](../specs/003-browser-offline-client/quickstart.md) for 6 end-to-end validation scenarios.
