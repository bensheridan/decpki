# Feature Specification: BFF Persistent Storage

**Feature Branch**: `008-bff-persistent-storage`

**Created**: 2026-06-28

**Status**: Draft

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Sessions Survive Restart (Priority: P1)

A developer running the demo BFF restarts the server process (e.g. after a code change) and their
existing browser session continues to work without requiring re-login. Refresh tokens issued before
the restart remain valid; protected endpoints keep returning data.

**Why this priority**: The current behaviour — all sessions wiped on restart — makes the demo
unusable in any setting where the server is restarted between browser interactions, and makes
automated tests that restart the BFF unreliable.

**Independent Test**: Register a passkey, log in, restart the BFF, call the protected `/api/me`
endpoint — it MUST return 200 without re-authentication.

**Acceptance Scenarios**:

1. **Given** a user has an active session, **When** the BFF process restarts, **Then** the user's
   session token and refresh token remain valid and the user does not need to log in again.
2. **Given** a refresh token was issued before restart, **When** the client refreshes the token
   after restart, **Then** a new session token is issued successfully.
3. **Given** the BFF has never been started before, **When** it starts for the first time,
   **Then** it initialises an empty store and begins accepting requests normally.

---

### User Story 2 — Revocations Are Durable (Priority: P2)

An administrator revokes a session via `DELETE /api/sessions/{id}`. After the BFF restarts, the
revoked session remains invalid — the revoked JWT ID is not reinstated.

**Why this priority**: Revocation that survives only until the next restart provides no real
security guarantee and undermines the session management feature.

**Independent Test**: Log in, revoke the session via the Sessions UI, restart the BFF, attempt to
use the revoked session token against a protected endpoint — it MUST return 401.

**Acceptance Scenarios**:

1. **Given** a session has been revoked, **When** the BFF restarts, **Then** any attempt to use
   the revoked session token still returns 401.
2. **Given** multiple sessions for a DID exist and one is revoked, **When** the BFF restarts,
   **Then** only the revoked session is blocked; the others continue to work.

---

### User Story 3 — Active Challenge Expiry Is Respected After Restart (Priority: P3)

Login challenges that were issued before a restart are treated correctly: unexpired challenges can
still be completed, and expired challenges are rejected.

**Why this priority**: Without this, a restart during the authenticator prompt flow causes a
confusing "challenge not found" error even though the user's timing was valid.

**Independent Test**: Issue a login challenge, restart the BFF within the challenge TTL, complete
the WebAuthn assertion — it MUST succeed.

**Acceptance Scenarios**:

1. **Given** a login challenge was created before a restart, **When** the restart happens within
   the challenge TTL and the assertion is submitted, **Then** the login completes successfully.
2. **Given** a login challenge was created before a restart and its TTL has elapsed, **When** the
   assertion is submitted after restart, **Then** the BFF rejects it with an appropriate error.

---

### Edge Cases

- What happens if the storage file/database is deleted between restarts? The BFF MUST start cleanly
  with an empty state rather than crashing.
- What happens if the storage file is corrupt or unreadable? The BFF MUST log a warning and start
  with empty state rather than refusing to start.
- What happens if two BFF processes start simultaneously against the same storage? Concurrent writes
  MUST not corrupt the stored state (file locking or equivalent).
- What happens during a write when the process is killed? The storage MUST not enter a permanently
  broken state; it MUST be recoverable on the next start.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The BFF MUST persist session state (refresh tokens, JTI blocklist, DID-to-session
  index) to durable storage so that it survives process restarts.
- **FR-002**: The BFF MUST persist active login challenges to durable storage so that they survive
  restarts within their TTL.
- **FR-003**: The BFF MUST restore all persisted state on startup before accepting requests.
- **FR-004**: Expired challenges MUST still be rejected after a restart (expiry checking MUST use
  stored timestamps, not in-memory creation time).
- **FR-005**: Revoked JWT IDs in the JTI blocklist MUST remain blocked after a restart for the
  remainder of their original TTL.
- **FR-006**: The storage location MUST be configurable via an environment variable with a safe
  default suitable for local development.
- **FR-007**: If the storage is absent or unreadable on startup, the BFF MUST start with empty
  state and log a clear warning rather than failing to start.
- **FR-008**: Concurrent access to storage from the same process MUST be safe (no race conditions
  on reads/writes within a single BFF instance).
- **FR-009**: The existing in-memory session and challenge behaviour (TTLs, revocation semantics,
  DID indexing) MUST be preserved exactly — only the backing store changes.

### Key Entities

- **Session Record**: A single active login — holds refresh token, DID, issued-at/expires-at
  timestamps, and last JTI. Identified by a token prefix (session_id).
- **Challenge Record**: A pending WebAuthn login challenge — holds raw challenge bytes, DID,
  credential ID, algorithm, and expiry timestamp.
- **JTI Blocklist Entry**: A revoked JWT ID plus the time it was added and its original expiry,
  used to reject revoked tokens until they would have expired naturally.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A session established before a BFF restart remains usable within 5 seconds of the
  server coming back online, with no user interaction required.
- **SC-002**: 100% of revoked sessions stay revoked across restarts — zero reinstatements.
- **SC-003**: BFF startup time increases by no more than 500 ms compared to the in-memory baseline
  when restoring up to 1 000 sessions.
- **SC-004**: No data loss occurs for sessions or revocations written more than 1 second before an
  ungraceful process termination.

## Assumptions

- A single BFF process serves all requests (no horizontal scaling requirement for this feature).
- The demo environment has a writable local filesystem; networked or read-only filesystems are out
  of scope.
- No migration of existing in-memory state is required — sessions active at the time of upgrade
  will be lost once, which is acceptable for a demo environment.
- The JTI blocklist only needs to retain entries until the corresponding JWT's natural expiry; the
  implementation may prune older entries on startup to keep storage small.
- Challenge TTL is short (60 seconds by default); challenges do not need to survive restarts longer
  than that window, but MUST still be checked against their stored expiry if they do persist.
