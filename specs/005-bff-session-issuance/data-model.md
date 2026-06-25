# Data Model: BFF Session Issuance

## Entities

### LoginChallenge (in-memory, BFF)

A short-lived nonce issued at login initiation. Single-use. Stored in a Python dict keyed by the raw challenge bytes (hex string).

| Field | Type | Description |
|-------|------|-------------|
| `challenge_hex` | `string` | 32 random bytes, hex-encoded. Used as the dict key and returned to the browser as base64url. |
| `did` | `string` | The DID of the user attempting login. |
| `credential_id` | `string (base64url)` | The credential ID from the enrolled passkey (used to identify which authenticator should respond). |
| `public_key_hex` | `string` | The enrolled ed25519 public key hex (32 bytes). Used to verify the assertion. |
| `issued_at` | `int (Unix timestamp)` | When the challenge was issued. |
| `expires_at` | `int (Unix timestamp)` | Challenge expiry (60 seconds after issuance). |

**Lifecycle**: Created by `POST /login/start`. Consumed (and deleted) by `POST /login/complete`. Expired challenges are lazily purged on access.

---

### SessionToken (self-contained JWT)

A signed, self-contained token issued on successful login. The BFF verifies these without a store lookup.

**JWT payload fields**:

| Field | Type | Description |
|-------|------|-------------|
| `sub` | `string` | The user's DID (e.g. `did:local:<uuid4>`). |
| `jti` | `string (UUID4)` | Unique token ID (for future blocklist support). |
| `iat` | `int (Unix timestamp)` | Issued-at time. |
| `exp` | `int (Unix timestamp)` | Expiry time. Default: `iat + 900` (15 minutes). |
| `type` | `string` | Always `"session"`. |

Signed with HS256 using `SESSION_SECRET` environment variable.

---

### RefreshToken (in-memory, BFF)

An opaque server-tracked token that allows the browser to obtain a new session token without a WebAuthn prompt. Stored in a Python dict keyed by the token value.

| Field | Type | Description |
|-------|------|-------------|
| `token` | `string (64 hex chars)` | 32 random bytes, hex-encoded. Used as the dict key and returned to the browser. |
| `did` | `string` | The DID this token is bound to. |
| `issued_at` | `int (Unix timestamp)` | When the token was issued. |
| `expires_at` | `int (Unix timestamp)` | Expiry. Default: `issued_at + 604800` (7 days). |

**Lifecycle**: Created alongside the session token at `POST /login/complete`. Deleted by `POST /login/logout`. Silently deleted if expired on access.

---

### RevokedToken

Not a separate store in the prototype — logout is implemented by deleting the `RefreshToken` entry. Session tokens cannot be individually revoked (self-contained); the maximum post-logout exposure is the session token lifetime (15 minutes, configurable). See research.md Decision 7.

---

## State Transitions

```
Login flow:

  [Browser calls POST /login/start with DID]
          ↓
   LoginChallenge created (TTL 60s)
          ↓
  [Browser completes WebAuthn assertion]
          ↓
   POST /login/complete:
     - Verify assertion signature
     - Verify DID in trust bundle
     - Delete LoginChallenge (single-use)
          ↓
   SessionToken + RefreshToken issued
          ↓
  [Browser stores tokens, schedules refresh]
          ↓
   (token nearing expiry) → POST /login/refresh
     - Verify RefreshToken exists + not expired
     - Re-verify DID in trust bundle
     - Issue new SessionToken (RefreshToken unchanged)
          ↓
   (explicit logout) → POST /login/logout
     - Delete RefreshToken
     - SessionToken expires naturally (max 15 min)
```

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `SESSION_SECRET` | — (required) | HS256 signing key for JWT session tokens. Must be at least 32 bytes. |
| `SESSION_LIFETIME_SECONDS` | `900` | Session token validity (15 minutes). |
| `REFRESH_LIFETIME_SECONDS` | `604800` | Refresh token validity (7 days). |
| `BUNDLE_PATH` | `/tmp/bundle.cbor` | Path to the trust bundle CBOR file. |
| `BUNDLE_REFRESH_INTERVAL` | `300` | How often (seconds) the BFF reloads the bundle from disk. |
