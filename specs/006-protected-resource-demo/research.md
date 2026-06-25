# Research: Protected Resource Demo

## Decision 1: Endpoint path — `/api/me`

**Decision**: Use `GET /api/me` as the protected resource endpoint.

**Rationale**: `/api/me` is the industry-standard "current user" endpoint pattern (used by GitHub, Slack, Auth0, etc.). It is instantly recognisable, signals that the response is about the authenticated caller, and communicates the demo's purpose without explanation.

**Alternatives considered**:
- `/api/profile` — also conventional but implies richer data than we have.
- `/api/protected` — generic; doesn't communicate what the resource is.
- `/login/me` — confusing since `/login/*` is the auth namespace.

---

## Decision 2: Response shape — DID + session metadata only

**Decision**: Return `{ "did", "issued_at", "expires_at", "message" }` — no additional user data.

**Rationale**: The prototype has no user profile store. The DID is the identity. Adding a human-readable `message` field ("Hello, did:local:…") makes the demo self-explanatory in the browser. `issued_at` and `expires_at` are already in the JWT payload (no extra work).

**Alternatives considered**:
- Returning a richer mock profile (name, email) — adds fake data that could mislead about the system's actual capabilities.
- Returning just the DID — too terse to read meaningfully in the demo UI.

---

## Decision 3: Token validation — reuse `verify_session_token` from Feature 005

**Decision**: Call `_session_store.verify_session_token(token)` directly. Do not re-verify the trust bundle.

**Rationale**: The JWT was issued only after the trust bundle confirmed the DID was active. Re-checking the bundle on every resource call would require I/O and add latency. The known revocation lag (up to 15 minutes post-logout) is documented and accepted in Feature 005. This is consistent with how all major JWT-based systems work.

**Alternatives considered**:
- Re-checking `bundle_cache.is_did_active()` on every `/api/me` call — adds latency, reduces benefit of self-contained JWT, and contradicts the Feature 005 design decision.

---

## Decision 4: Where to extract the Bearer token — `Authorization` header

**Decision**: Read `Authorization: Bearer <token>` from the request header, same as `GET /login/verify`.

**Rationale**: Standard HTTP convention. The browser already sets this header in Feature 005's `getToken()` flow. Consistent with the existing `/login/verify` pattern.

**Alternatives considered**: Query parameter — insecure (token appears in server logs and browser history).

---

## Decision 5: Demo UI — update existing button, do not add a new one

**Decision**: Change the `btnVerify` click handler in `login.html` to call `GET /api/me` instead of `GET /login/verify`. Display the full JSON response.

**Rationale**: Adding a second button would clutter the demo. The existing button's label ("Call Protected Endpoint") already implies a real resource, not a token verification utility. Updating the target makes the label accurate.

**Alternatives considered**: Keep both buttons — adds visual noise without explanatory value for a demo.
