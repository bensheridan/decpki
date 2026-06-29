# Data Model: BFF Persistent Storage

## Entities

### Challenge

Represents a pending WebAuthn login challenge issued to a client. Short-lived (60 s TTL).

| Field | Type | Notes |
|---|---|---|
| `challenge_hex` | string (64 hex chars) | Primary key; 32 random bytes |
| `did` | string | DID of the identity being authenticated |
| `credential_id` | string | WebAuthn credential ID (base64url) |
| `public_key_hex` | string | Stored public key for the credential |
| `algorithm` | string | `"ed25519"` or `"es256"` |
| `issued_at` | integer (Unix seconds) | Creation time |
| `expires_at` | integer (Unix seconds) | `issued_at + 60` |

**Lifecycle**: Created on `POST /login/start`. Consumed (deleted) when `POST /login/complete`
is called. Rows with `expires_at < now` are pruned on startup and can also be purged lazily on
read.

---

### RefreshToken

Represents an active device session. Long-lived (default 7 days).

| Field | Type | Notes |
|---|---|---|
| `token_hex` | string (64 hex chars) | Primary key; 32 random bytes |
| `did` | string | Indexed; links session to an identity |
| `issued_at` | integer | Creation time |
| `expires_at` | integer | `issued_at + REFRESH_LIFETIME_SECONDS` |
| `last_jti` | string | Most recent session JWT ID issued against this token; used for revocation |

**Lifecycle**: Created on `POST /login/complete`. Consumed on `POST /login/logout` or
`DELETE /api/sessions/{id}`. The `last_jti` field is updated each time a new session token is
minted via `POST /login/refresh`.

**Derived index**: `did` → set of `token_hex` values (computed at query time via `SELECT
token_hex FROM refresh_tokens WHERE did = ?`).

---

### JTIBlocklistEntry

Records a revoked session JWT ID to prevent its reuse until natural expiry.

| Field | Type | Notes |
|---|---|---|
| `jti` | string (UUID4) | Primary key |
| `added_at` | integer | When the revocation was recorded |
| `original_exp` | integer | When the JWT would have expired; used for pruning |

**Lifecycle**: Written when a session is revoked. Pruned on startup (and optionally lazily)
when `original_exp < now`.

---

## Relationships

```
RefreshToken ──── (did) ────► identity (external — stored in promoted enrolment files)
RefreshToken ──── (last_jti) ──► JTIBlocklistEntry (on revocation only)
Challenge    ──── (did, credential_id) ──► promoted enrolment files (external)
```

No foreign-key constraints are enforced in the store itself — the BFF layer is responsible
for consistency.
