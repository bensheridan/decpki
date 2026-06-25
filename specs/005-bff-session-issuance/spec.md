# Feature Specification: BFF Session Issuance

**Feature Branch**: `005-bff-session-issuance`

**Created**: 2026-06-25

**Status**: Draft

**Input**: User description: "Feature 005 — BFF Session Issuance — the other half of the FIDO2 flow. A user registers a passkey (Feature 004), but there's no login yet. Feature 005 would add: browser presents a WebAuthn assertion → BFF verifies it against the trust bundle → issues a short-lived JWT session token."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Log In with a Registered Passkey (Priority: P1)

A user who has already registered a FIDO2 credential (Feature 004) visits the service and initiates login. Their device prompts for biometric confirmation or PIN. The BFF receives the resulting cryptographic assertion, verifies it against the stored credential public key and the current trust bundle, and issues a short-lived session token. The browser stores this token and includes it on subsequent requests.

**Why this priority**: Without login, Feature 004 enrolment is a dead end. This closes the loop from registration to authenticated access and is the minimum viable auth flow.

**Independent Test**: A user who completed Feature 004 registration can complete login — a valid session token is issued, included in a subsequent request, and the request is accepted. The entire flow works without any server-side session state beyond the token itself.

**Acceptance Scenarios**:

1. **Given** a user has an enrolled passkey, **When** they initiate login and confirm with biometric/PIN, **Then** the BFF returns a signed session token and the browser stores it.
2. **Given** a valid session token, **When** the browser makes a protected request with the token, **Then** the request is accepted.
3. **Given** a session token past its expiry time, **When** the browser presents it, **Then** the request is rejected and the user is prompted to log in again.
4. **Given** a user whose DID has been revoked (excluded from the current trust bundle), **When** they attempt login, **Then** the login is rejected — the trust bundle is the authoritative source.
5. **Given** a login attempt using a credential whose assertion signature does not verify, **Then** the login is rejected with an appropriate error.

---

### User Story 2 - Silent Token Refresh (Priority: P2)

Before a session token expires, the browser automatically obtains a fresh one without requiring the user to re-authenticate with their device. The refresh uses a longer-lived refresh token issued alongside the original session token.

**Why this priority**: A 15-minute session lifetime (reasonable for security) would otherwise require the user to re-authenticate frequently. Silent refresh makes the session feel continuous without degrading the security model.

**Independent Test**: A session token approaching expiry is silently replaced by the browser; the user experiences no interruption and no biometric prompt is shown.

**Acceptance Scenarios**:

1. **Given** a session token with < 2 minutes remaining, **When** the browser makes any request, **Then** a background refresh is triggered and the new token is stored before the old one expires.
2. **Given** a refresh token, **When** it is presented to the BFF, **Then** a new session token is issued without requiring a WebAuthn assertion.
3. **Given** a refresh token that has expired or been revoked, **When** presented, **Then** the refresh is rejected and the user must log in again with their passkey.
4. **Given** a user whose DID was revoked between token issuance and refresh, **When** refresh is attempted, **Then** the refresh is rejected — the BFF re-checks the trust bundle on every refresh.

---

### User Story 3 - Explicit Logout (Priority: P3)

A user can log out, immediately invalidating their session token and refresh token. Subsequent requests using those tokens are rejected.

**Why this priority**: Without logout, tokens are only invalidated by expiry. Logout is essential for shared-device scenarios and for a complete auth flow.

**Independent Test**: After logout, a previously valid session token is rejected within one token lifetime.

**Acceptance Scenarios**:

1. **Given** a valid session token, **When** the user logs out, **Then** the session and refresh tokens are invalidated server-side.
2. **Given** an invalidated session token, **When** it is presented to a protected endpoint, **Then** the request is rejected.
3. **Given** a user is logged out on one browser tab, **When** another tab attempts to use the old token, **Then** the request is rejected.

---

### Edge Cases

- What happens if the trust bundle has expired (not yet refreshed) when a login is attempted?
- What happens if two login attempts are made simultaneously from the same device?
- What happens if the WebAuthn challenge times out (user takes too long to confirm)?
- How does the system behave if the BFF loses its revoked-token store on restart?
- What happens if a user tries to refresh with a session token (not a refresh token)?

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The BFF MUST issue a server-side challenge (nonce) at the start of each login attempt; the challenge MUST be single-use and expire within 60 seconds.
- **FR-002**: The browser MUST present a WebAuthn assertion (signed challenge) to the BFF to authenticate; the BFF MUST verify the assertion signature using the credential public key stored from enrolment (Feature 004).
- **FR-003**: Before issuing a session token, the BFF MUST verify that the user's DID is present and active in the current trust bundle. If the DID is absent or the bundle is expired, login MUST be rejected.
- **FR-004**: On successful authentication, the BFF MUST issue a short-lived session token (default lifetime: 15 minutes) and a longer-lived refresh token (default lifetime: 7 days).
- **FR-005**: The session token MUST encode the user's DID and expiry; it MUST be verifiable by the BFF without a database lookup (self-contained signed token).
- **FR-006**: The refresh token MUST be tracked server-side so it can be revoked explicitly (logout) or invalidated when the DID is revoked in the trust bundle.
- **FR-007**: The BFF MUST re-verify the trust bundle on every token refresh — a DID revoked after initial login MUST be rejected at refresh time.
- **FR-008**: Logout MUST immediately invalidate both the session token and the refresh token; the BFF MUST reject any subsequent request presenting those tokens.
- **FR-009**: Session tokens MUST be transmitted over HTTPS only; the BFF MUST set appropriate security headers (HttpOnly, Secure, SameSite) if tokens are delivered as cookies, or document the expected header if delivered as JSON.
- **FR-010**: The login challenge MUST be bound to the specific credential (the BFF issues it for a known credential ID or DID, not as an open challenge).

### Key Entities

- **LoginChallenge**: A short-lived server-side nonce issued at login initiation, bound to a DID or credential ID, single-use, expires in 60 seconds.
- **SessionToken**: A self-contained signed token encoding the user's DID and expiry. Verifiable without a database lookup. Lifetime: 15 minutes (configurable).
- **RefreshToken**: A server-tracked opaque token associated with a DID and session. Lifetime: 7 days (configurable). Revocable.
- **RevokedToken**: A record of invalidated refresh tokens, used to enforce logout and DID revocation. Checked on every refresh attempt.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A user with a registered passkey can complete login (challenge → assertion → token) in under 10 seconds on a device with biometric support.
- **SC-002**: 100% of login attempts where the DID is absent from the trust bundle are rejected — no false positives.
- **SC-003**: A revoked DID is denied login within one bundle refresh cycle (bounded by the configured bundle validity window, per existing revocation policy).
- **SC-004**: Silent token refresh completes in under 2 seconds and is invisible to the user (no UI interruption, no biometric prompt).
- **SC-005**: After explicit logout, the invalidated tokens are rejected within one session token lifetime (≤ 15 minutes).
- **SC-006**: Zero session tokens are issued for assertions that fail cryptographic verification.

## Assumptions

- The BFF from Feature 004 is extended — this feature adds login endpoints to the same service rather than introducing a separate auth server.
- The trust bundle is loaded by the BFF at startup and refreshed periodically (configurable interval); the BFF does not make a live chain query on every login.
- Refresh tokens are stored in-memory in the BFF process for the prototype (acceptable; lost on restart). A production deployment would use a persistent store.
- Session tokens are delivered as JSON in the response body (not cookies) for the prototype, to simplify the demo. Cookie delivery is noted as a production hardening step.
- The login flow identifies the user by DID; the browser must know the user's DID before initiating login (it was returned at registration time and should be stored by the client application).
- Token signing uses a symmetric secret key held by the BFF (not a validator keypair — session tokens are BFF-internal, not chain-recorded). Key rotation is a future concern.
- The existing `DecPKIClient` browser library is unchanged; the new `DecPKISession` JS module handles login and token management.
- Mobile native app support is out of scope; this feature targets browser-based WebAuthn login only.
