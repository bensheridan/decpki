# Data Model: Session Management

## Entities

### ActiveSession (in-memory, BFF)

Represents one logged-in device/browser. Backed by a refresh token entry in `SessionStore._refresh_tokens`, extended with `last_jti`.

| Field | Type | Description |
|-------|------|-------------|
| `session_id` | `string (16 hex chars)` | First 16 characters of the refresh token hex. Unique enough for list display; cannot reconstruct the full token. Used as the URL parameter in `DELETE /api/sessions/{session_id}`. |
| `did` | `string` | The DID this session is bound to. |
| `issued_at` | `int (Unix timestamp)` | When the refresh token (and therefore the session) was created. |
| `expires_at` | `int (Unix timestamp)` | Refresh token expiry. |
| `last_jti` | `string (UUID4)` | The `jti` of the most recently issued session token for this refresh token. Added to the `jti` blocklist on revocation. |
| `is_current` | `bool` | True if this session matches the caller's refresh token. Set by the list endpoint at response time — not stored. |

**Lifecycle**: Created by `POST /login/complete` (via `issue_refresh_token`). Deleted by `POST /login/logout` or `DELETE /api/sessions/{session_id}`. Silently cleaned up on expiry during access.

---

### JtiBlocklist (in-memory, BFF)

A set of revoked JWT unique IDs. Checked on every protected endpoint call.

| Field | Type | Description |
|-------|------|-------------|
| `jti` | `string (UUID4)` | The unique token ID from a revoked session token's JWT payload. |

**Lifecycle**: Entry added when a session is revoked via `DELETE /api/sessions/{session_id}`. Entries are never removed (prototype trade-off — the set grows until BFF restart). At prototype scale (handful of sessions) this is negligible.

---

### SessionIndex (in-memory, BFF)

Secondary index for DID → session lookup.

| Field | Type | Description |
|-------|------|-------------|
| key | `string (DID)` | The user's DID. |
| value | `set[string]` | Full refresh token hex strings for all active sessions belonging to this DID. |

**Lifecycle**: Entry added in `issue_refresh_token`. Entry removed in `revoke_refresh_token`. Lazily cleaned on expired-entry access.

---

## State Transitions

```
Session lifecycle:

  POST /login/complete
       ↓
  RefreshToken created (→ ActiveSession entry)
  SessionToken issued (jti stored as last_jti)
       ↓
  [Session token nears expiry]
       ↓
  POST /login/refresh
  → new SessionToken issued, last_jti updated
       ↓
  [User views sessions]
       ↓
  GET /api/sessions (requires Bearer token + refresh_token body)
  → returns list of ActiveSession with is_current flag
       ↓
  [User revokes a session]
       ↓
  DELETE /api/sessions/{session_id}
  → last_jti added to JtiBlocklist
  → RefreshToken deleted from _refresh_tokens and _sessions_by_did
  → If revoking current session: caller is effectively logged out
       ↓
  [Protected endpoint called with revoked token]
       ↓
  jti check → 401 Unauthorized
```

---

## Changes to Existing Entities (Feature 005)

### RefreshToken (extended)

The `RefreshToken` dict entry in `SessionStore._refresh_tokens` gains one field:

| New Field | Type | Description |
|-----------|------|-------------|
| `last_jti` | `string (UUID4)` | Updated each time a new session token is issued for this refresh token. Populated in `issue_session_token`. |

### SessionStore (extended methods)

| New Method | Signature | Description |
|------------|-----------|-------------|
| `list_sessions(did)` | `-> list[dict]` | Returns all active (non-expired) refresh token entries for the given DID, formatted as ActiveSession records. |
| `revoke_session(session_id)` | `-> bool` | Finds the refresh token matching the 16-char prefix, adds `last_jti` to the blocklist, deletes the token entry. Returns `True` if found, `False` if not. |
| `is_jti_revoked(jti)` | `-> bool` | Returns `True` if the `jti` is in the blocklist. |

`issue_session_token` is updated to accept an optional `refresh_token_hex` parameter and update `last_jti` in the corresponding refresh token entry.
