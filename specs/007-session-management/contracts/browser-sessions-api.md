# Browser Sessions API Contract

The `sessions.js` module exports a single class `DecPKISessions`.

## Import

```js
import { DecPKISessions } from './sessions.js';
```

## Constructor

```js
const sessions = new DecPKISessions({
  bffBaseUrl: 'http://localhost:8000',  // HTTPS required (localhost excepted)
  session: decPKISessionInstance,       // DecPKISession instance (provides getToken(), getDid(), refresh token)
});
```

---

## Methods

### `list()`

Fetch all active sessions for the logged-in DID.

```js
const result = await sessions.list();
```

**Returns** `Promise<SessionListResult>`:

```ts
interface SessionEntry {
  sessionId: string;     // 16 hex chars — unique session identifier
  did: string;
  issuedAt: number;      // Unix timestamp
  expiresAt: number;     // Unix timestamp
  isCurrent: boolean;    // true if this is the caller's own session
}

interface SessionListResult {
  sessions: SessionEntry[];
}
```

**Throws**:
- `SessionsAuthError` — session token is missing or expired; user must re-login.

---

### `revoke(sessionId)`

Revoke a specific session by ID.

```js
const result = await sessions.revoke('abcd1234abcd1234');
```

**Returns** `Promise<{ ok: boolean, selfRevoked: boolean }>`.

- `selfRevoked: true` — the caller revoked their own session; the UI should log out.

**Throws**:
- `SessionsAuthError` — caller's session is expired or already revoked.
- `SessionNotFoundError` — target session not found (already revoked or expired).

---

### `addDevice()`

Initiate enrolment of a new passkey for the current DID, without navigating away from the session management page.

```js
const result = await sessions.addDevice();
```

**Returns** `Promise<AddDeviceResult>`:

```ts
interface AddDeviceResult {
  requestId: string;
  did: string;
  status: 'pending';
  threshold: number;
  signaturesCollected: number;
}
```

**Throws**:
- `AddDeviceCancelledError` — user dismissed the biometric/PIN prompt.
- `AddDeviceError` — enrolment request could not be created (device not supported, duplicate credential, etc.).

---

## Error Classes

| Class | Meaning |
|-------|---------|
| `SessionsAuthError` | Caller's session token is invalid or expired |
| `SessionNotFoundError` | Target session not found or already revoked |
| `AddDeviceCancelledError` | User cancelled the WebAuthn prompt during Add New Device |
| `AddDeviceError` | Add New Device failed for a non-cancellation reason |
