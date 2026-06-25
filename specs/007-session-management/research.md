# Research: Session Management

## Decision 1: Immediate revocation with self-contained JWTs — jti blocklist

**Decision**: Maintain an in-memory `_jti_blocklist: set[str]` in `SessionStore`. Every call to a protected endpoint checks this set before returning a response. `revoke_session(session_id)` adds the `jti` to the blocklist and deletes the associated refresh token entry.

**Rationale**: JWTs are self-contained — a server cannot "reach into" an issued token to invalidate it. The only way to achieve immediate revocation (SC-002: "within 1 second") is a server-side blocklist. The `jti` field (unique token ID, a UUID4) was included in Feature 005's JWT payload precisely for this future use. Checking a set membership is O(1) and adds negligible latency.

**Alternatives considered**:
- Short session lifetime (e.g., 1 minute) — removes need for blocklist but means users must re-authenticate frequently; doesn't meet SC-002's "within 1 second" requirement for in-flight tokens.
- Database-backed blocklist — overkill for a prototype; loses the simplicity advantage of in-memory state.
- Reference tokens (opaque, always server-side lookup) — would fully solve the problem but requires replacing the JWT system from Feature 005, which is a larger change than the feature warrants.

---

## Decision 2: Session identity = refresh token entry, exposed via truncated ID

**Decision**: Each "session" in the management UI corresponds to one refresh token entry. The session list endpoint returns a session ID (first 16 hex chars of the refresh token — enough to be unique but not enough to reconstruct the full token), plus `did`, `issued_at`, `expires_at`, and an `is_current` flag.

**Rationale**: One login → one refresh token → one session. This is already the natural unit of session in Feature 005. Reusing the refresh token as the session record avoids a new data structure. Exposing only a prefix of the token hex prevents a compromised session list response from being used to forge refresh token calls.

**Alternatives considered**:
- Separate session ID (UUID) stored alongside the refresh token — cleaner separation but adds a new dict and another field to manage; unnecessary for a prototype.
- Returning the full refresh token in the session list — security risk; a stolen session list response would allow refreshing any session.

---

## Decision 3: DID-indexed lookup — secondary index in SessionStore

**Decision**: Add `_sessions_by_did: dict[str, set[str]]` to `SessionStore`, mapping DID → set of refresh token hex strings. Maintained alongside `_refresh_tokens`: added in `issue_refresh_token`, removed in `revoke_refresh_token` and `consume_refresh_token` (when expired).

**Rationale**: The existing `_refresh_tokens` dict is keyed by token value, not DID. To list all sessions for a DID without scanning the entire dict, a secondary index is the standard approach. A `dict[str, set[str]]` is lightweight and consistent with the prototype's in-memory model.

**Alternatives considered**:
- Full dict scan on every session list request — acceptable at prototype scale (handful of entries), but creates a bad pattern to carry forward.
- Storing DID as a top-level key in a new dict — same as the chosen approach, just named differently.

---

## Decision 4: `is_current` flag — matched by refresh token in request header

**Decision**: The session list endpoint requires the caller's refresh token (passed in the request body alongside the session JWT). The endpoint compares each session entry's token prefix against the caller's refresh token prefix to set `is_current = true` on the matching entry.

**Rationale**: The server cannot know which session is "current" from the JWT alone — the `jti` identifies the session token, not the refresh token, and a refresh token maps to multiple session tokens over time. Asking the client to include its refresh token in the list request solves this without storing additional state. The token is already in `localStorage` and is never logged or returned in the response.

**Alternatives considered**:
- Using `jti` of the Bearer session token to identify "current" — ambiguous after a refresh (the session token changes but the refresh token stays the same).
- Storing a "last-used session token jti" per refresh entry — more state to maintain; adds complexity without clear benefit.

---

## Decision 5: Add New Device — reuse `DecPKIRegistration.addCredential()`

**Decision**: The **Add New Device** button in `sessions.html` calls `DecPKIRegistration.addCredential(did)` from Feature 004's `registration.js`, passing the currently logged-in DID. The sessions page imports both `session.js` (to get the DID and token) and `registration.js` (to trigger enrolment).

**Rationale**: Feature 004 already implemented the full `addCredential` flow: ownership proof via existing credential, new credential COSE extraction, enrolment request creation. Reusing it avoids duplicating WebAuthn logic. The sessions page is simply a new entry point into the same flow.

**Alternatives considered**:
- Re-implementing the enrolment flow in `sessions.js` — code duplication; violates DRY.
- Redirecting to `register.html?did=…` — loses the single-page feel; the user navigates away from session management.

---

## Decision 6: Revocation scope — revoke all tokens for a session

**Decision**: `DELETE /api/sessions/{session_id}` revokes both the refresh token (deleted from `_refresh_tokens` and `_sessions_by_did`) and all session tokens issued from it (by adding associated `jti` values to the blocklist). Since the prototype does not store which `jti` values were issued per refresh token, the blocklist is populated with the `jti` of the most recently issued session token (stored in the refresh token entry as `last_jti`).

**Rationale**: A revoked session must not be usable — this requires invalidating both the refresh token (prevents new session tokens) and the currently-live session token (prevents continued access with the in-flight token). Storing `last_jti` in the refresh token entry adds one field and solves the problem without a separate data structure.

**Alternatives considered**:
- Only deleting the refresh token — the current session token would remain valid until expiry (up to 15 min). Violates SC-002.
- Storing all `jti` values ever issued per refresh token — unnecessary; only the latest in-flight token needs blocking.
