# Browser Registration API Contract

The `registration.js` module exposes a single class `DecPKIRegistration` alongside the existing `DecPKIClient`.

## Import

```js
import { DecPKIRegistration } from './registration.js';
```

## Constructor

```js
const reg = new DecPKIRegistration({
  bffBaseUrl: 'https://your-bff.example/enrolment',  // required; HTTPS enforced (localhost excepted)
  rpId: 'your-bff.example',                           // optional; defaults to window.location.hostname
});
```

### Config

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `bffBaseUrl` | `string` | — | Base URL of the BFF enrolment API. Must be HTTPS (localhost exempted). |
| `rpId` | `string` | `window.location.hostname` | WebAuthn relying-party ID. |

---

## Methods

### `register()`

Create a new FIDO2 credential and submit it for enrolment.

```js
const result = await reg.register();
```

**Returns** `Promise<RegistrationResult>`:

```ts
interface RegistrationResult {
  requestId: string;      // UUID4 of the pending EnrolmentRequest
  did: string;            // Assigned DID (did:local:<uuid4>)
  status: 'pending';      // Always 'pending' on fresh submission
  threshold: number;      // Number of validator signatures required
  signaturesCollected: number; // Always 0 on fresh submission
  expiresAt: number;      // Unix timestamp
}
```

**Throws**:
- `RegistrationCancelledError` — user cancelled the biometric/PIN prompt.
- `AlgorithmNotSupportedError` — device does not support ed25519 credentials.
- `RegistrationError` — BFF rejected the submission (e.g., duplicate credential).

---

### `addCredential(existingDid)`

Add a new credential to an existing DID. Requires an existing valid credential to prove ownership.

```js
const result = await reg.addCredential('did:local:<uuid4>');
```

**Returns** same `RegistrationResult` shape as `register()`.

**Throws**:
- `OwnershipProofFailedError` — the assertion for the existing DID failed.
- All errors from `register()`.

---

### `getStatus(requestId)`

Poll the status of a pending enrolment request.

```js
const status = await reg.getStatus('<request-id>');
```

**Returns** `Promise<EnrolmentStatus>`:

```ts
interface EnrolmentStatus {
  requestId: string;
  did: string;
  status: 'pending' | 'promoted' | 'expired' | 'cancelled';
  signaturesCollected: number;
  threshold: number;
  expiresAt: number;
}
```

---

## Error Classes

| Class | Meaning |
|-------|---------|
| `RegistrationCancelledError` | User dismissed the authenticator prompt |
| `AlgorithmNotSupportedError` | Device cannot create ed25519 credentials |
| `OwnershipProofFailedError` | Assertion for existing DID was invalid |
| `RegistrationError` | BFF returned a non-retryable error (message property contains detail) |

---

## CLI Commands (decpki extension)

### `decpki enrol-sign`

A validator signs a pending enrolment request.

```bash
decpki enrol-sign \
  --request /tmp/decpki-enrolments/<uuid4>.json \
  --validator /tmp/alpha.key.json
```

Appends the validator's signature to the request file in-place. Prints the updated signature count and threshold.

### `decpki enrol-promote`

Promote a fully co-signed request to a ledger identity record.

```bash
decpki enrol-promote \
  --request /tmp/decpki-enrolments/<uuid4>.json \
  --threshold 2
```

Verifies quorum, writes an `IdentityRecord` to the local ledger store, and moves the request file to `/tmp/decpki-enrolments/promoted/`. Prints the resulting DID and identity record summary.

After promotion, run `decpki bundle` as usual to include the new identity in the trust bundle.
