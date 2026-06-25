# Tasks: Session Management

**Input**: Design documents from `specs/007-session-management/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Organization**: Tasks are grouped by user story to enable independent implementation and testing.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3)

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Extend the session store with the new data structures that all three user stories depend on. Must be complete before any story work begins.

- [X] T001 Extend `SessionStore` in `bff/session.py`: add `_jti_blocklist: set[str]` field; add `_sessions_by_did: dict[str, set[str]]` secondary index; add `is_jti_revoked(jti: str) -> bool` method (returns `True` if jti in blocklist); update `issue_refresh_token` to also insert the token hex into `_sessions_by_did[did]`; update `revoke_refresh_token` to also remove from `_sessions_by_did`
- [X] T002 Update `issue_session_token` in `bff/session.py` to accept an optional `refresh_token_hex: str | None = None` parameter; when provided, update `_refresh_tokens[refresh_token_hex]["last_jti"]` with the new token's `jti`; always include `jti` in the JWT payload (already present from Feature 005 — verify this and add `last_jti` field initialised to `""` when a new refresh token entry is created in `issue_refresh_token`)
- [X] T003 Add `list_sessions(did: str) -> list[dict]` to `SessionStore` in `bff/session.py`: iterate `_sessions_by_did.get(did, set())`, look up each token in `_refresh_tokens`, skip expired entries (where `int(time.time()) > entry["expires_at"]`), return list of dicts with `session_id` (first 16 hex chars of token), `did`, `issued_at`, `expires_at`, `last_jti`
- [X] T004 Add `revoke_session(session_id: str) -> tuple[bool, str | None]` to `SessionStore` in `bff/session.py`: scan `_refresh_tokens` for a token whose hex starts with `session_id`; if not found return `(False, None)`; add `entry["last_jti"]` to `_jti_blocklist` if non-empty; call `revoke_refresh_token(token_hex)`; return `(True, token_hex)`
- [X] T005 Update `GET /login/verify` and `GET /api/me` in `bff/main.py` to check `_session_store.is_jti_revoked(payload["jti"])` after successful JWT decode — return 401 with `"Session has been revoked"` if revoked

---

## Phase 2: Foundational — Wire Blocklist into All Protected Endpoints

**Purpose**: Ensure the jti blocklist is enforced everywhere before any UI work begins. Failing to do this before US2 would leave a gap where revoked tokens could still access resources.

**⚠️ CRITICAL**: T005 in Phase 1 covers `/login/verify` and `/api/me`. Confirm both check `is_jti_revoked` before proceeding.

- [X] T006 Add `GET /api/sessions` endpoint to `bff/main.py`: accept `Authorization: Bearer <token>` header and request body `{"refresh_token": "..."}` (use a Pydantic model `SessionListRequest`); verify JWT (with jti check); call `_session_store.list_sessions(payload["sub"])`; compute `is_current` for each entry by comparing `entry["session_id"]` against the first 16 chars of the request body `refresh_token`; return `{"sessions": [...]}` per `contracts/bff-sessions-api.md`
- [X] T007 Add `DELETE /api/sessions/{session_id}` endpoint to `bff/main.py`: accept `Authorization: Bearer <token>` header and path param `session_id`; verify JWT (with jti check); call `_session_store.revoke_session(session_id)`; return 404 if not found; determine `self_revoked` by checking if the revoked entry's `last_jti` matches `payload["jti"]`; return `{"ok": True, "self_revoked": <bool>}` per `contracts/bff-sessions-api.md`

**Checkpoint**: `python3 -c "from session import SessionStore; s = SessionStore(); t,e=s.issue_session_token('did:test'); print(s.is_jti_revoked('fake-jti'))"` prints `False`. Confirmed that `/login/verify` and `/api/me` both return 401 when called with a token whose jti is in the blocklist.

---

## Phase 3: User Story 1 — View Active Sessions (Priority: P1) 🎯 MVP

**Goal**: A logged-in user opens `sessions.html` and sees all active sessions for their DID, with the current session clearly identified.

**Independent Test**: Run quickstart.md Scenario 1 — log in, open `sessions.html`, see at least one session marked **This device**.

- [X] T008 [P] [US1] Create `browser/src/sessions.js`: export `DecPKISessions` class and error classes `SessionsAuthError`, `SessionNotFoundError`, `AddDeviceCancelledError`, `AddDeviceError`; implement constructor `({ bffBaseUrl, session })` with HTTPS enforcement (localhost excepted); implement `list()` method: calls `GET {bffBaseUrl}/api/sessions` with `Authorization: Bearer <token>` (from `session.getToken()`) and body `{"refresh_token": localStorage.getItem("decpki_refresh")}`; maps response to camelCase `SessionEntry[]`; throws `SessionsAuthError` on 401
- [X] T009 [P] [US1] Create `browser/demo/sessions.html`: title "DecPKI — Session Management"; nav links to `index.html`, `login.html`, `sessions.html`; session list `<ul id="sessionList">` showing each session as `<li>` with issued-at date, `[This device]` badge if `isCurrent`, and a **Revoke** button (disabled for current session — enabled in US2); **Add New Device** button (stub — enabled in US3); `#status` div for feedback; imports `session.js` and `sessions.js` via ESM; on load calls `session.isLoggedIn()` — if false, shows "Please log in first" with link to `login.html`; on load calls `sessions.list()` and renders results; uses `textContent` only (XSS safe)
- [X] T010 [US1] Update `browser/demo/server.mjs`: add route for `/sessions.html` (same pattern as `/login.html`); `/api/*` proxy already added in Feature 006 — verify it covers the new session endpoints
- [X] T011 [US1] Add link to `sessions.html` from `browser/demo/login.html`: add `<a href="/sessions.html">Manage Sessions</a>` in the nav `<nav>` element

**Checkpoint**: Run quickstart.md Scenario 1. Session list renders with at least one entry. Current session shows **This device**.

---

## Phase 4: User Story 2 — Revoke an Individual Session (Priority: P2)

**Goal**: A logged-in user can revoke any session from the list. Revocation is immediate — the revoked token is rejected by all protected endpoints. Self-revocation logs the user out.

**Independent Test**: Run quickstart.md Scenarios 3 and 4 — revoke another tab's session (tab B gets 401) and revoke current session (page logs out immediately).

- [X] T012 [US2] Implement `revoke(sessionId)` method in `browser/src/sessions.js`: calls `DELETE {bffBaseUrl}/api/sessions/{sessionId}` with `Authorization: Bearer <token>`; throws `SessionsAuthError` on 401; throws `SessionNotFoundError` on 404; returns `{ ok, selfRevoked }`
- [X] T013 [US2] Wire **Revoke** buttons in `browser/demo/sessions.html`: each session `<li>` has a **Revoke** button enabled for all sessions (including the current one); click handler calls `sessions.revoke(sessionId)`; on success: if `selfRevoked`, calls `session.logout()` then shows "You have been logged out" and redirects to `login.html` after 2 seconds; if not `selfRevoked`, refreshes the session list; on error: displays message in `#status`; disable button during in-progress call to prevent duplicate submissions

**Checkpoint**: Run quickstart.md Scenarios 3 and 4. Tab B session gets 401 after revocation from tab A. Self-revocation triggers logout in the current tab.

---

## Phase 5: User Story 3 — Add a Second Passkey (Priority: P3)

**Goal**: A logged-in user can initiate enrolment of a new passkey for their existing DID directly from the session management page.

**Independent Test**: Run quickstart.md Scenario 5 — click **Add New Device** in `sessions.html`, complete WebAuthn prompt, see enrolment request confirmation.

- [X] T014 [US3] Implement `addDevice()` method in `browser/src/sessions.js`: imports `DecPKIRegistration` from `./registration.js`; creates a `DecPKIRegistration` instance with `bffBaseUrl` pointing to the enrolment base URL (`bffBaseUrl.replace('/login', '') + '/enrolment'` or equivalent); calls `reg.addCredential(session.getDid())`; maps `RegistrationCancelledError` → `AddDeviceCancelledError`; maps other `RegistrationError` → `AddDeviceError`; returns the enrolment result
- [X] T015 [US3] Wire **Add New Device** button in `browser/demo/sessions.html`: click handler calls `sessions.addDevice()`; on success shows confirmation with `requestId` in `#status`; on `AddDeviceCancelledError` shows "Registration cancelled"; on `AddDeviceError` shows the error message; disables button during the operation

**Checkpoint**: Run quickstart.md Scenario 5. Pending enrolment request appears in `GET /enrolment/` for the existing DID.

---

## Phase 6: Polish & Cross-Cutting Concerns

- [X] T016 [P] Write `bff/tests/test_sessions.py`: unit tests for `SessionStore` extensions — `issue_refresh_token` populates `_sessions_by_did`; `revoke_refresh_token` removes from `_sessions_by_did`; `is_jti_revoked` returns `True` after revocation; `list_sessions` skips expired entries; `revoke_session` returns `(False, None)` for unknown session_id. Integration tests via FastAPI TestClient: `GET /api/sessions` returns session list; `DELETE /api/sessions/{id}` returns `{"ok": true}`; revoked session token returns 401 on `/api/me` and `/login/verify`; `DELETE /api/sessions/{id}` for unknown ID returns 404
- [X] T017 [P] Write `browser/tests/unit/sessions.test.js`: mock `fetch` and `DecPKIRegistration`; test `list()` returns `SessionEntry[]`; `list()` throws `SessionsAuthError` on 401; `revoke()` returns `selfRevoked: true` when server says so; `revoke()` throws `SessionNotFoundError` on 404; `addDevice()` returns result on success; `addDevice()` throws `AddDeviceCancelledError` on `RegistrationCancelledError`
- [X] T018 Update root `README.md`: add Feature 007 to the status table; add session management to the **How it works** section (step 8: "Users can view and revoke active sessions per device")
- [X] T019 Update `browser/README.md`: add **Session Management** section documenting `DecPKISessions` usage, link to `sessions.html` demo

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — T001–T005 must complete before any story work
- **Foundational (Phase 2)**: Depends on Phase 1 — T006–T007 (BFF endpoints) block US1 (can't list sessions without the endpoint)
- **US1 (Phase 3)**: Depends on Phase 2; T008 and T009 can run in parallel (different files)
- **US2 (Phase 4)**: Depends on US1 (revoke button is wired in sessions.html created in US1)
- **US3 (Phase 5)**: Depends on US1 (Add New Device button stub created in US1); independent of US2
- **Polish (Phase 6)**: Depends on desired stories complete

### Parallel Opportunities

- T001–T004 (Phase 1): All touch `bff/session.py` — run sequentially
- T008 (sessions.js) and T009 (sessions.html) — different files, run in parallel
- T016 (BFF tests) and T017 (browser tests) — run in parallel
- T018 and T019 (READMEs) — run in parallel

---

## Implementation Strategy

### MVP (US1 only — T001–T011)

1. Extend `SessionStore` with index and list/revoke methods (T001–T004)
2. Wire jti blocklist into protected endpoints (T005)
3. Add BFF session list endpoint (T006)
4. Create `sessions.js` and `sessions.html` (T008–T009)
5. Update server.mjs and add nav link (T010–T011)
6. **STOP and VALIDATE**: quickstart.md Scenario 1 — session list renders

### Incremental Delivery

1. Setup + Foundational (T001–T007): infrastructure + BFF endpoints
2. US1 (T008–T011): session list UI
3. US2 (T012–T013): revocation + self-revocation logout
4. US3 (T014–T015): Add New Device
5. Polish (T016–T019): tests + docs

---

## Notes

- `[P]` tasks touch different files with no blocking dependencies within their phase
- T005 (jti blocklist enforcement) is the highest-risk task — it modifies two existing working endpoints (`/login/verify`, `/api/me`). Test carefully with valid tokens before adding the blocklist check.
- The `DELETE /api/sessions/{session_id}` body does not require the refresh token — the session_id prefix lookup is sufficient for revocation. Only the `GET /api/sessions` endpoint needs the refresh token body (to determine `is_current`).
- `revoke_session` must handle the race condition where two concurrent calls try to revoke the same session — the second call returns `(False, None)` because the token was already deleted by the first. This is the correct idempotent behaviour.
- The **Revoke** button for the current session should be labelled distinctively (e.g., "Sign out this device") to prevent accidental self-revocation.
