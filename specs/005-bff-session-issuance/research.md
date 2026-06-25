# Research: BFF Session Issuance

## Decision 1: Session Token Format (JWT with HS256)

**Decision**: Use JWT (JSON Web Token) with HS256 (HMAC-SHA256) symmetric signing for session tokens. The BFF signs and verifies with a shared secret held in an environment variable (`SESSION_SECRET`).

**Rationale**: JWT is self-contained — verification requires no database lookup, which keeps the hot path (request authentication) fast. HS256 is appropriate for BFF-internal tokens where the issuer and verifier are the same service. The token payload encodes `did`, `exp` (expiry), and `iat` (issued-at). `python-jose` provides a well-tested JWT implementation compatible with Python 3.11.

**Alternatives considered**:
- **Ed25519 asymmetric JWT (EdDSA)**: Would allow other services to verify tokens without the secret. Rejected — in this prototype the BFF is the only verifier; asymmetric adds complexity for no benefit.
- **Opaque session tokens (server-side store lookup)**: Every request would require a store lookup. Rejected — defeats the stateless goal and adds latency.
- **Paseto**: More modern than JWT; avoids JWT footguns. Rejected — library ecosystem less mature in Python; JWT is sufficient for a prototype and widely understood.

---

## Decision 2: Refresh Token Design (Opaque, Server-Tracked)

**Decision**: Refresh tokens are random 32-byte hex strings stored in an in-memory dict keyed by token value, with value `{did, expires_at, session_token_jti}`. On refresh, the BFF looks up the token, re-checks the trust bundle, and issues a new session token. On logout, the entry is deleted.

**Rationale**: Refresh tokens must be revocable (logout, DID revocation), so they cannot be self-contained like session tokens. Opaque tokens are simpler to invalidate than JWT refresh tokens (no blocklist needed — just delete the entry). For the prototype, in-memory storage is sufficient; a production deployment would use Redis or a database.

**Alternatives considered**:
- **JWT refresh tokens**: Would need a blocklist to support logout. Rejected — adds complexity without benefit in the prototype.
- **Single-use refresh tokens (rotation)**: Each refresh consumes the old token and issues a new one. Improves security (replay detection). Noted as a future hardening step; not implemented in prototype for simplicity.

---

## Decision 3: WebAuthn Assertion Verification (Python)

**Decision**: Use the `cryptography` library (already a dependency) to verify the ed25519 assertion signature directly. The BFF extracts the `authenticatorData` and `clientDataJSON` from the assertion, computes the verification data (`authenticatorData || SHA-256(clientDataJSON)`), and verifies the signature using the stored credential public key bytes.

**Rationale**: The `cryptography` library already supports ed25519 public key verification (`Ed25519PublicKey.verify()`). This avoids adding a new dependency. The WebAuthn assertion signature covers `authenticatorData || SHA-256(clientDataJSON)` per the W3C spec — this is the standard verification procedure for step-7 of the authentication ceremony.

**Alternatives considered**:
- **`@simplewebauthn/server` (Node.js)**: Would require a Node.js sidecar or rewriting the BFF in Node. Rejected — Python BFF is established.
- **`py_webauthn`**: A full WebAuthn server library for Python. Would handle all ceremony steps automatically. Considered but rejected for the prototype because it adds a heavyweight dependency for a flow we control end-to-end; direct verification with `cryptography` is transparent and auditable.

---

## Decision 4: Trust Bundle Loading in the BFF

**Decision**: `bundle_cache.py` loads the trust bundle from a CBOR file at startup (path from `BUNDLE_PATH` env var, defaulting to `/tmp/bundle.cbor`) and caches it in memory. A background thread refreshes the cache every `BUNDLE_REFRESH_INTERVAL` seconds (default: 300). Login and refresh both read from the in-memory cache.

**Rationale**: Loading the bundle from disk on every request would be slow and would fail if the bundle file is momentarily being written by `decpki bundle`. An in-memory cache with periodic refresh is a standard pattern. The refresh interval should be shorter than the bundle validity period to ensure the cache is reasonably fresh.

**Alternatives considered**:
- **Live chain query on every login**: Would require a running chain node. Rejected — offline-first principle; the bundle is the source of truth.
- **Reload on every request**: Simple but slow (CBOR parse on every login). Rejected.
- **File watch (inotify/kqueue)**: More reactive than polling. Noted as a future improvement; polling is simpler and sufficient for the prototype.

---

## Decision 5: Login Challenge Binding

**Decision**: Login challenges are issued per-DID: `POST /login/start` takes the user's DID, looks up their credential public key from promoted enrolments, generates a 32-byte random challenge, stores `{challenge, credential_id, public_key_hex, expires_at}` keyed by challenge value, and returns the challenge. The challenge is bound to the specific DID's credential — only that credential's assertion will verify.

**Rationale**: Binding the challenge to a DID prevents an attacker from obtaining a generic challenge and replaying it with a different credential. Single-use (deleted after first use) prevents replay. 60-second TTL limits the window.

**Alternatives considered**:
- **Open challenge (not DID-bound)**: Simpler (no DID lookup at start). Rejected — weaker binding; an assertion from any registered credential would pass.
- **Challenge in cookie/session**: Would require cookies at the login initiation step. Rejected — stateless challenge (in-memory dict) is simpler.

---

## Decision 6: Browser Session Storage

**Decision**: The `DecPKISession` JS class stores the session token and refresh token in `localStorage` (keyed by `decpki_session` and `decpki_refresh`). It schedules a silent refresh using `setTimeout` when the session token has 2 minutes remaining.

**Rationale**: `localStorage` survives page reloads and is accessible across tabs (needed for US3 logout). `sessionStorage` would be lost on tab close. IndexedDB is overkill for two small strings. The existing `DecPKIClient` uses IndexedDB for the bundle — session tokens are a different concern.

**Security note**: `localStorage` is accessible to JavaScript, making it vulnerable to XSS. For a production deployment, HttpOnly cookies are recommended (tokens never touch JS). Documented as a known limitation of the prototype; the demo does not have an XSS attack surface since it serves no user-generated content.

**Alternatives considered**:
- **HttpOnly cookies**: Immune to XSS. Rejected for prototype (requires same-origin BFF serving, more complex CORS setup). Noted as the recommended production approach.
- **In-memory only (no persistence)**: Token lost on page reload. Rejected — would require re-authentication on every page load.

---

## Decision 7: Logout Token Invalidation

**Decision**: Logout deletes the refresh token from the in-memory store. Session tokens cannot be individually revoked (self-contained JWT), so they remain technically valid until expiry. The maximum residual validity after logout is the session token lifetime (15 minutes default). This is documented as an accepted tradeoff for the prototype.

**Rationale**: True session token revocation requires a blocklist checked on every request, which adds latency and complexity. For a 15-minute token lifetime, the exposure window after logout is bounded and acceptable for a prototype. Production deployments should use a blocklist or shorter token lifetimes.

**Alternatives considered**:
- **JWT ID (jti) blocklist**: Store revoked `jti` values and check on every verification. Rejected for prototype — adds a lookup on every request.
- **Very short session token lifetime (e.g., 1 minute)**: Minimises post-logout exposure. Could be combined with the current approach. Noted as a configurable option via `SESSION_LIFETIME_SECONDS` env var.
