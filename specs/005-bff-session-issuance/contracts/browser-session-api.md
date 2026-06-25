# Browser Session API Contract

The `session.js` module exports a single class `DecPKISession`.

## Import

```js
import { DecPKISession } from './session.js';
```

## Constructor

```js
const session = new DecPKISession({
  bffBaseUrl: 'https://your-bff.example/login',  // required; HTTPS enforced (localhost excepted)
});
```

---

## Methods

### `login(did)`

Initiate a WebAuthn authentication ceremony and exchange the assertion for a session token.

```js
const result = await session.login('did:local:<uuid4>');
```

**Returns** `Promise<SessionResult>`:

```ts
interface SessionResult {
  did: string;
  sessionToken: string;
  refreshToken: string;
  expiresAt: number;        // Unix timestamp
  refreshExpiresAt: number; // Unix timestamp
}
```

**Throws**:
- `LoginCancelledError` — user dismissed the biometric/PIN prompt.
- `LoginFailedError` — BFF rejected the assertion (wrong credential, revoked DID, expired challenge). `message` property contains detail.
- `DIDNotFoundError` — DID not found in promoted enrolments.

---

### `refresh()`

Exchange the stored refresh token for a new session token. Called automatically before expiry.

```js
const result = await session.refresh();
```

**Returns** `Promise<{ sessionToken: string, did: string, expiresAt: number }>`.

**Throws**:
- `SessionExpiredError` — refresh token is expired or invalidated; user must call `login()` again.

---

### `logout()`

Invalidate the refresh token server-side and clear stored tokens.

```js
await session.logout();
```

**Returns** `Promise<void>`.

---

### `getToken()`

Return the current session token, triggering a silent refresh if expiry is within 2 minutes.

```js
const token = await session.getToken();
// Use as: Authorization: Bearer <token>
```

**Returns** `Promise<string | null>`. Returns `null` if not logged in.

---

### `getDid()`

Return the DID encoded in the current session token, or `null` if not logged in.

```js
const did = session.getDid(); // synchronous — reads from stored token
```

**Returns** `string | null`.

---

### `isLoggedIn()`

Return `true` if a non-expired session token is stored.

```js
if (session.isLoggedIn()) { ... }
```

**Returns** `boolean`.

---

## Error Classes

| Class | Meaning |
|-------|---------|
| `LoginCancelledError` | User dismissed the WebAuthn prompt |
| `LoginFailedError` | BFF rejected login (assertion failed, revoked DID, expired challenge) |
| `DIDNotFoundError` | DID not found when initiating login |
| `SessionExpiredError` | Refresh token expired; must re-authenticate |

---

## Storage

Tokens are stored in `localStorage`:

| Key | Value |
|-----|-------|
| `decpki_session` | JWT session token string |
| `decpki_refresh` | Refresh token hex string |
| `decpki_did` | The logged-in DID |
| `decpki_expires_at` | Session token expiry (Unix timestamp, string) |

The class reads these keys on construction, so a page reload preserves the session if the token has not expired.
