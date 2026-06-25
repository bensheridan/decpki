# Feature Specification: Session Management

**Feature Branch**: `007-session-management`

**Created**: 2026-06-25

**Status**: Draft

**Input**: User description: "Feature 007 — Multi-device / Session Management UI: list active sessions per DID (which devices are logged in), revoke individual sessions, and trigger an enrolment for a second passkey from the login page rather than the registration page."

## User Scenarios & Testing *(mandatory)*

### User Story 1 — View Active Sessions (Priority: P1)

A logged-in user opens a session management view and can see all currently active sessions for their DID — effectively a list of which devices or browsers are logged in. Each session entry shows enough context to identify it (when it was created, approximate last activity) so the user can distinguish between their own devices.

**Why this priority**: Before a user can revoke a session, they must be able to see the sessions that exist. This is the foundational read operation that all other stories depend on.

**Independent Test**: Log in from two different browser tabs. Open the session management view. Both sessions are listed. The current session is clearly identified.

**Acceptance Scenarios**:

1. **Given** a user is logged in with a valid session, **When** they open the session management view, **Then** they see a list of all active sessions for their DID, including the current one.
2. **Given** a user has one active session, **When** they view the session list, **Then** the current session is labelled or highlighted so it is distinguishable from others.
3. **Given** a session has expired or been revoked, **When** the user views the session list, **Then** that session no longer appears.
4. **Given** the user is not logged in, **When** they try to view the session list, **Then** they are shown an authentication-required message rather than the session list.

---

### User Story 2 — Revoke an Individual Session (Priority: P2)

A logged-in user selects a specific session from the list and revokes it. The revoked session can no longer be used to access protected resources. This is the primary security action — "sign out of that other device."

**Why this priority**: Session revocation is the security-critical action this feature exists to provide. Without it, the list view has no practical payoff.

**Independent Test**: Log in from two tabs. In tab A, revoke the session shown for tab B. In tab B, click **Call Protected Endpoint** — receive a rejection indicating the session is invalid. Tab A session remains usable.

**Acceptance Scenarios**:

1. **Given** a user sees a session in their list, **When** they click **Revoke** on that session, **Then** the session is removed from the list and can no longer be used.
2. **Given** a user revokes their own current session, **When** the revocation completes, **Then** they are automatically logged out of the current view.
3. **Given** a revoked session token is used to call a protected endpoint, **When** the request arrives, **Then** the endpoint rejects it with an authentication-required response.
4. **Given** the user clicks **Revoke**, **When** the operation is in progress, **Then** a visual indicator (spinner or disabled button) prevents duplicate submissions.

---

### User Story 3 — Add a Second Passkey (Enrol New Device) (Priority: P3)

A logged-in user initiates enrolment of a second passkey directly from the session management view, without navigating to the separate registration page. This covers the "I just got a new device and want to add it" scenario.

**Why this priority**: This completes the multi-device lifecycle — a user with an existing identity can expand access to a new device without starting over. It depends on P1 (the session view provides the entry point) and reuses the Feature 004 enrolment flow.

**Independent Test**: Log in on device A. From the session management view, click **Add New Device**. Complete the WebAuthn registration prompt. A new enrolment request appears in the pending queue (visible via `GET /enrolment/`). After validator co-signing and promotion, logging in from device B succeeds.

**Acceptance Scenarios**:

1. **Given** a logged-in user is on the session management view, **When** they click **Add New Device**, **Then** they are prompted for a biometric/PIN to register a new passkey credential.
2. **Given** the user completes the credential registration, **When** the request is submitted, **Then** a pending enrolment request is created for their existing DID, and the user is shown a confirmation with the request ID.
3. **Given** the user cancels the biometric/PIN prompt, **When** cancellation is detected, **Then** no enrolment request is created and a clear cancellation message is shown.
4. **Given** the device's authenticator does not support the required credential type, **When** the user attempts to add a new device, **Then** a clear, non-technical error message is shown.

---

### Edge Cases

- What happens when a user tries to revoke the only session while also being logged in via that session? The system should allow it (self-revocation) and log the user out immediately.
- What happens if the session list is fetched but the server-side store has been restarted (losing in-memory sessions)? The list returns empty — this is an accepted prototype limitation of in-memory storage.
- What happens if two requests to revoke the same session are submitted simultaneously? The second revocation is a no-op (idempotent), matching the behaviour of the existing logout endpoint.
- What happens if the user's DID has been revoked from the trust bundle between login and viewing sessions? The session view request will return an authentication-required response if the endpoint re-validates the token; the user will need to contact a validator to restore access.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST provide a view that lists all active sessions associated with the currently authenticated DID.
- **FR-002**: Each session entry MUST display when it was created and an indicator of whether it is the current session.
- **FR-003**: The session list MUST only be accessible to authenticated users — unauthenticated requests MUST be rejected.
- **FR-004**: A user MUST be able to revoke any individual session from the list, including their current session.
- **FR-005**: Revoking the current session MUST immediately log the user out of the management view.
- **FR-006**: A revoked session token MUST be rejected by all protected endpoints immediately after revocation.
- **FR-007**: The **Revoke** action MUST be protected against duplicate submissions while in progress.
- **FR-008**: A logged-in user MUST be able to initiate enrolment of a new passkey for their existing DID directly from the session management view.
- **FR-009**: The new-device enrolment flow MUST create a pending enrolment request for the user's existing DID (not a new DID).
- **FR-010**: The session management view MUST be reachable from the login page without requiring a separate navigation step.

### Key Entities

- **ActiveSession**: A currently valid server-side session record. Contains session identifier, DID, creation time, and last-activity time. Distinguished from the self-contained JWT — requires a server-side store to support revocation.
- **SessionRevocation**: The act of invalidating an ActiveSession. Once revoked, the associated session identifier is permanently invalid.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A user can view all active sessions for their DID and identify the current session within 2 seconds of opening the session management view.
- **SC-002**: A revoked session is rejected by all protected endpoints within 1 second of the revocation completing — no grace window after revocation.
- **SC-003**: A user can initiate enrolment of a new passkey from the session management view without navigating away from the page.
- **SC-004**: 100% of revocation attempts result in either successful revocation or a clear error message — silent failures are unacceptable.
- **SC-005**: The session management view is accessible from the login page in one click.

## Assumptions

- Session revocation requires a server-side session store (not just JWTs) — the existing in-memory refresh token store from Feature 005 will be extended to serve as the session registry. This is an accepted prototype limitation (sessions are lost on BFF restart).
- "Active session" in this context means an unexpired refresh token entry — each login creates one refresh token, which represents one logged-in session. Session identity is the refresh token identifier.
- The session list shows sessions by DID — the BFF must be able to look up all refresh tokens for a given DID, which requires indexing the in-memory store by DID.
- "Last activity" is approximated by the refresh token's `issued_at` and most recent token refresh time (if tracked). For the prototype, `issued_at` of the refresh token is sufficient.
- The "Add New Device" flow reuses the Feature 004 `addCredential` path from `DecPKIRegistration` — no new enrolment logic is needed, only a new entry point from the session management UI.
- The current session is identified by matching the session token's `jti` (unique token ID) against the active session list — or more practically, by comparing the refresh token stored in `localStorage` against the list returned by the server.
- Mobile browser support is not in scope.
