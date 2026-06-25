# Feature Specification: Protected Resource Demo

**Feature Branch**: `006-protected-resource-demo`

**Created**: 2026-06-25

**Status**: Draft

**Input**: User description: "Feature 006 — Protected Resource Demo: a small example API route that validates the user's session token and returns data about the authenticated user. Closes the loop from login → accessing a real protected endpoint."

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Access a Protected Resource with a Valid Session (Priority: P1)

A logged-in user clicks a button in the demo UI. The demo sends their session token to a server-side endpoint. The server validates the token and responds with information about the authenticated identity — confirming that only verified, trust-bundle-backed users can access protected data.

**Why this priority**: This is the entire point of the feature — completing the login-to-resource-access loop. Without this, the login flow has no visible payoff.

**Independent Test**: Can be fully tested by logging in via `login.html` and clicking **Call Protected Endpoint** — the response panel shows the authenticated DID and token expiry. Delivers a tangible end-to-end demo.

**Acceptance Scenarios**:

1. **Given** a user has logged in and holds a valid session token, **When** they request the protected endpoint, **Then** the endpoint returns their DID and session details with a success response.
2. **Given** a user has logged in, **When** they click the **Call Protected Endpoint** button, **Then** the response is displayed in the demo UI without a page reload.
3. **Given** a logged-in user's DID has been revoked and the bundle has been updated, **When** the bundle check is performed at login, **Then** the token was never issued — the resource endpoint itself does not need to re-check the bundle on every call (token validation is sufficient for session endpoints).

---

### User Story 2 — Reject Requests Without a Valid Token (Priority: P2)

An unauthenticated request (missing or expired token) to the protected endpoint is rejected. The demo UI shows a clear error message distinguishing "not logged in" from "session expired".

**Why this priority**: Security enforcement at the resource layer is not optional — a demo that accepts requests without valid tokens is misleading about the system's security properties.

**Independent Test**: Can be tested independently by calling the endpoint with no token, a tampered token, and an expired token via curl — each returns a distinct, actionable error.

**Acceptance Scenarios**:

1. **Given** no session token is present, **When** the protected endpoint is called, **Then** the response is a rejection with a message indicating authentication is required.
2. **Given** a tampered or malformed session token is submitted, **When** the protected endpoint is called, **Then** the response is a rejection with a message indicating the token is invalid.
3. **Given** an expired session token is submitted, **When** the protected endpoint is called, **Then** the response is a rejection with a message indicating the session has expired.
4. **Given** the demo UI detects a rejection, **When** the result is displayed, **Then** the UI shows a human-readable message (not a raw error object) and does not expose internal token details.

---

### Edge Cases

- What happens when the session token is structurally valid but signed with the wrong key? The endpoint must reject it as invalid.
- What happens when the token has not yet expired but the underlying DID was revoked after login? The token remains valid until expiry — this is the known revocation lag, documented in the login spec.
- What happens if the endpoint is called with an `Authorization` header that is present but malformed (e.g. `Bearer` with no token)? The endpoint must reject it with a clear error.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST provide a protected endpoint that returns the authenticated user's DID and session expiry when called with a valid session token.
- **FR-002**: The protected endpoint MUST reject any request that does not include a valid, non-expired session token, returning a response that indicates authentication is required.
- **FR-003**: The demo UI MUST include a button that calls the protected endpoint using the currently stored session token and displays the response to the user.
- **FR-004**: The demo UI MUST display a distinct, human-readable message for each rejection case: not authenticated, invalid token, and expired session.
- **FR-005**: The protected endpoint MUST NOT accept tokens that have been tampered with or signed by an unrecognised key.
- **FR-006**: The demo UI button MUST be disabled (or show a clear inactive state) when no session is active, preventing accidental calls without a token.

### Key Entities

- **SessionToken**: The short-lived credential issued at login. Contains the user's DID and expiry. Used as the proof of authentication for the protected endpoint.
- **ProtectedResource**: The server-side endpoint and its response. Returns identity information for the authenticated user.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A logged-in user can access the protected endpoint and see their DID in the response within 1 second of clicking the button.
- **SC-002**: A request with no token, an expired token, or a tampered token is rejected 100% of the time with a human-readable error displayed in the UI.
- **SC-003**: A non-technical observer watching the demo can narrate the full flow — "register passkey → log in → access protected resource → log out" — in under 2 minutes without prompting.
- **SC-004**: The **Call Protected Endpoint** button is never clickable when the user is not logged in.

## Assumptions

- The session token issued by the BFF (Feature 005) is the authentication mechanism — no new credential type is introduced.
- The protected endpoint returns the user's DID and session expiry; it does not query external systems or databases.
- The demo UI already has a **Call Protected Endpoint** button from Feature 005's `login.html`; this feature changes what it calls (a real resource endpoint instead of the token verification utility endpoint).
- The revocation lag for active session tokens (up to 15 minutes post-logout) is accepted as a known prototype limitation, consistent with the Feature 005 design decision.
- Mobile browser support is not in scope — the demo targets desktop browsers.
