# Tasks: Protected Resource Demo

**Input**: Design documents from `specs/006-protected-resource-demo/`

**Prerequisites**: plan.md, spec.md, research.md, contracts/bff-api.md, quickstart.md

**Organization**: Tasks are grouped by user story to enable independent implementation and testing.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2)

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: No new dependencies or skeleton files are needed — this feature extends existing modules. Phase 1 is a single verification step.

- [X] T001 Verify `bff/main.py` imports `Header` from `fastapi` and `JWTError` from `jose` — both already present from Feature 005; confirm no new requirements needed

---

## Phase 2: User Story 1 — Access a Protected Resource with a Valid Session (Priority: P1) 🎯 MVP

**Goal**: A logged-in user clicks **Call Protected Endpoint**, receives their DID and session details in the response panel.

**Independent Test**: Run quickstart.md Scenario 1 — log in via `login.html`, click **Call Protected Endpoint** → HTTP 200 with DID in response displayed in UI.

- [X] T002 [US1] Implement `GET /api/me` in `bff/main.py`: read `Authorization: Bearer <token>` header (using `Header(default=None)`), call `_session_store.verify_session_token(token)`, return 401 on missing header or `JWTError`, return 200 with `{"did": payload["sub"], "issued_at": payload["iat"], "expires_at": payload["exp"], "message": f"Hello, {payload['sub']}"}` matching `contracts/bff-api.md`
- [X] T003 [US1] Update the `btnVerify` click handler in `browser/demo/login.html`: change the fetch target from `/login/verify` to `/api/me` (keep the same `Authorization: Bearer <token>` header); the response display logic is unchanged
- [X] T004 [US1] Write `bff/tests/test_api_me.py`: test valid token returns 200 with correct DID and message; test missing Authorization header returns 401; test malformed token (no "Bearer " prefix) returns 401; test tampered token returns 401

**Checkpoint**: Run quickstart.md Scenario 1 — click **Call Protected Endpoint** → `{"did": "did:local:…", "message": "Hello, did:local:…"}` displayed. Run `pytest bff/tests/test_api_me.py` → all pass.

---

## Phase 3: User Story 2 — Reject Requests Without a Valid Token (Priority: P2)

**Goal**: Every unauthenticated or invalid-token request is rejected with a clear, human-readable error in the demo UI.

**Independent Test**: Run quickstart.md Scenarios 2, 3, 4 — each returns HTTP 401 with a distinct message; the demo UI displays the message without exposing raw token data.

- [X] T005 [US2] Confirm that `GET /api/me` (T002) already handles all rejection cases per `contracts/bff-api.md`: missing header → 401 `"Missing or invalid Authorization header"`, malformed token → 401 from `JWTError`, expired token → 401 from `JWTError` (`ExpiredSignatureError`). Add inline comments in `bff/main.py` only if the error path is non-obvious.
- [X] T006 [US2] Update the error display in `browser/demo/login.html`: when `/api/me` returns a non-200 response, extract `detail` from the JSON body (or use a fallback message) and display it via `textContent` in the `#status` div with the `error` CSS class. Ensure raw token strings are never inserted into the DOM.

**Checkpoint**: Run quickstart.md Scenarios 2–4 via curl and via the UI button (with a forced expired token using `SESSION_LIFETIME_SECONDS=5`) — each shows a distinct human-readable error in the UI.

---

## Phase 4: Polish & Cross-Cutting Concerns

- [X] T007 [P] Verify `btnVerify` is disabled when `session.isLoggedIn()` is false — check `login.html`'s `updateButtons()` function; `btnVerify.disabled = !loggedIn` must be set after logout and on page load when no session is stored
- [X] T008 [P] Update `browser/demo/server.mjs` to proxy `/api/*` to the BFF at port 8000 (same pattern as `/enrolment/*` and `/login/*`)
- [X] T009 Update root `README.md`: add `GET /api/me` to the **How it works** section and Feature 006 to the status table
- [X] T010 Update `browser/README.md`: add a note in the **Session / Login** section that `getToken()` is used to call `/api/me` as the example protected resource

---

## Dependencies & Execution Order

- **Phase 1** (T001): Verification only — no blocking work
- **Phase 2** (T002–T004): Depends on T001 confirmation; T002 (BFF) and T003 (browser) can run in parallel after T001; T004 (tests) depends on T002
- **Phase 3** (T005–T006): Depends on T002 (endpoint must exist to validate rejection behaviour)
- **Phase 4** (T007–T010): T007 and T008 can run in parallel; T009 and T010 are documentation and can run after T002

### Parallel Opportunities

- T002 (BFF endpoint) and T003 (login.html update) touch different files — run in parallel
- T007 and T008 (polish) touch different files — run in parallel

---

## Implementation Strategy

### MVP (User Story 1 only — T001–T004)

1. Verify setup (T001)
2. Implement `GET /api/me` in `bff/main.py` (T002)
3. Update `login.html` button target (T003)
4. Write and run tests (T004)
5. **STOP and VALIDATE**: quickstart.md Scenario 1

### Full delivery

1. MVP (T001–T004)
2. US2 error display (T005–T006)
3. Polish (T007–T010)

---

## Notes

- No new Python packages required — all imports are already present from Feature 005
- `GET /api/me` is intentionally simple: pure JWT decode, no I/O, no bundle re-check (documented trade-off)
- The `btnVerify` label ("Call Protected Endpoint") is already accurate once T003 is complete — no label change needed
- The proxy in `server.mjs` (T008) is required so the browser demo can reach `/api/me` via `http://localhost:3000/api/me` without a CORS issue
