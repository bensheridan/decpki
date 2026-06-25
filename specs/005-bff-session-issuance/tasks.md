# Tasks: BFF Session Issuance

**Input**: Design documents from `specs/005-bff-session-issuance/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3)

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Add new dependencies and create skeleton files before any story work begins.

- [X] T001 Add `python-jose[cryptography]` to `bff/requirements.txt` and run `pip install -r requirements.txt` in `bff/`
- [X] T002 [P] Create `bff/session.py` skeleton (empty: `SessionStore` class stub, `issue_session_token`, `verify_session_token`, `issue_refresh_token`, `consume_refresh_token`, `revoke_refresh_token` stubs)
- [X] T003 [P] Create `bff/bundle_cache.py` skeleton (empty: `BundleCache` class stub with `get_did` method stub)
- [X] T004 [P] Create `browser/src/session.js` skeleton (empty exports: `DecPKISession` class, error classes `LoginCancelledError`, `LoginFailedError`, `DIDNotFoundError`, `SessionExpiredError`)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Implement the shared infrastructure that all three user stories depend on — JWT signing, bundle cache, and session store. Must be complete before any story work begins.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [X] T005 Implement `bff/bundle_cache.py`: `BundleCache` class with `__init__(bundle_path, refresh_interval_seconds)`, `_load()` method that reads the CBOR file using `deserialise_bundle` from `src/decpki/bundle.py`, `start()` that launches a background `threading.Thread` calling `_load()` every `refresh_interval_seconds`, `get_did(did) -> IdentityRecord | None` that searches `bundle.identities` for an active (non-revoked) record matching the DID, and `is_did_active(did) -> bool`. Read `BUNDLE_PATH` and `BUNDLE_REFRESH_INTERVAL` env vars with defaults `/tmp/bundle.cbor` and `300`.
- [X] T006 Implement `bff/session.py`: `SessionStore` class with in-memory dicts `_challenges: dict[str, dict]` and `_refresh_tokens: dict[str, dict]`. Methods: `create_challenge(did, credential_id, public_key_hex) -> str` (generates 32-byte random hex challenge, stores with 60s TTL, returns challenge hex); `consume_challenge(challenge_hex) -> dict | None` (pops entry, returns None if missing or expired); `issue_session_token(did) -> tuple[str, int]` (signs HS256 JWT with `sub=did`, `jti=uuid4()`, `exp=now+SESSION_LIFETIME_SECONDS`, returns (token, exp)); `verify_session_token(token) -> dict` (decodes and validates JWT, raises `jose.JWTError` on failure); `issue_refresh_token(did) -> tuple[str, int]` (generates 32-byte random hex, stores with `REFRESH_LIFETIME_SECONDS` TTL, returns (token, exp)); `consume_refresh_token(token) -> dict | None` (returns entry without deleting — refresh keeps token alive); `revoke_refresh_token(token)` (deletes entry). Read `SESSION_SECRET`, `SESSION_LIFETIME_SECONDS=900`, `REFRESH_LIFETIME_SECONDS=604800` from env.
- [X] T007 Wire `BundleCache` and `SessionStore` singletons into `bff/main.py`: instantiate both in the `lifespan` handler alongside `EnrolmentStore`. Start `bundle_cache.start()` in lifespan. Add `bundle_cache` and `session_store` as module-level vars (initially `None`, set in lifespan).
- [X] T008 Implement assertion verification helper in `bff/session.py`: `verify_assertion(authenticator_data_b64, client_data_json_b64, signature_b64, public_key_hex, expected_challenge_b64) -> bool`. Decode base64url inputs. Verify `clientDataJSON.type == "webauthn.get"` and `clientDataJSON.challenge == expected_challenge_b64`. Compute verification data as `authenticatorData_bytes + SHA-256(clientDataJSON_bytes)`. Verify ed25519 signature using `cryptography`'s `Ed25519PublicKey.from_public_bytes(bytes.fromhex(public_key_hex)).verify(sig_bytes, verification_data)`. Return `True` on success, `False` on any failure (catch all exceptions).

**Checkpoint**: `python3 -c "from session import SessionStore; s = SessionStore(); print(s.issue_session_token('did:local:test'))"` prints a JWT. `python3 -c "from bundle_cache import BundleCache; b = BundleCache('/tmp/bundle.cbor', 300); b._load(); print('ok')"` prints `ok` if a bundle exists.

---

## Phase 3: User Story 1 — Log In with a Registered Passkey (Priority: P1) 🎯 MVP

**Goal**: A user with a registered passkey completes login — WebAuthn assertion → signature verification → trust bundle check → session + refresh token issued.

**Independent Test**: Run quickstart.md Scenario 1 end-to-end: log in via `login.html`, click **Call Protected Endpoint** → HTTP 200 with DID in response.

### Implementation for User Story 1

- [X] T009 [US1] Implement `POST /login/start` in `bff/main.py`: accept `{"did": "..."}`, look up the DID's promoted enrolment (scan `/tmp/decpki-enrolments/promoted/*.json`), return 404 if not found. Call `session_store.create_challenge(did, credential_id, public_key_hex)`. Return `{"challenge": <base64url(challenge_bytes)>, "allow_credentials": [{"type":"public-key","id":<credential_id>}], "user_verification": "preferred", "timeout": 60000}` matching `contracts/bff-login-api.md`.
- [X] T010 [US1] Implement `POST /login/complete` in `bff/main.py`: accept `{"did": ..., "assertion": {...}}`. Decode `clientDataJSON` to extract the challenge. Call `session_store.consume_challenge(challenge_hex)` — return 401 if None (expired/not found). Call `session_store.verify_assertion(...)` using the stored `public_key_hex` — return 401 if False. Call `bundle_cache.is_did_active(did)` — return 401 with `"DID not active in trust bundle"` if False. Call `session_store.issue_session_token(did)` and `session_store.issue_refresh_token(did)`. Return 200 with `{"session_token", "refresh_token", "did", "expires_at", "refresh_expires_at"}` matching `contracts/bff-login-api.md`.
- [X] T011 [US1] Implement `GET /login/verify` in `bff/main.py`: read `Authorization: Bearer <token>` header, call `session_store.verify_session_token(token)`, return 401 on `JWTError`, return 200 with `{"did": payload["sub"], "expires_at": payload["exp"]}`.
- [X] T012 [US1] Implement `DecPKISession` in `browser/src/session.js`: constructor validates `bffBaseUrl` (HTTPS / localhost). `login(did)` method: calls `POST {bffBaseUrl}/start` with `{did}`, passes response to `@simplewebauthn/browser`'s `startAuthentication({challenge, allowCredentials, userVerification})`, posts assertion to `POST {bffBaseUrl}/complete` with `{did, assertion}`, stores `session_token`, `refresh_token`, `did`, `expires_at` in `localStorage` under keys `decpki_session`, `decpki_refresh`, `decpki_did`, `decpki_expires_at`. Schedules silent refresh via `setTimeout` at `(expires_at - now - 120) * 1000` ms. Maps `NotAllowedError` → `LoginCancelledError`; BFF 401 → `LoginFailedError`; BFF 404 → `DIDNotFoundError`.
- [X] T013 [US1] Implement `getToken()` in `browser/src/session.js`: reads `decpki_session` from localStorage, parses `decpki_expires_at`, if expiry is within 120 seconds calls `this.refresh()` first, returns the token string or `null` if not logged in.
- [X] T014 [US1] Implement `getDid()` and `isLoggedIn()` in `browser/src/session.js`: `getDid()` reads `decpki_did` from localStorage; `isLoggedIn()` returns `true` if `decpki_session` exists and `decpki_expires_at > Date.now()/1000`.
- [X] T015 [US1] Create `browser/demo/login.html`: DID input, **Log In** button (calls `session.login(did)`), **Call Protected Endpoint** button (calls `GET /login/verify` with `Authorization: Bearer <token>` and displays response), **Log Out** button stub (enabled in US3). Displays logged-in DID and token expiry. Uses `textContent` only (XSS safe). Links to `register.html` and `index.html`.
- [X] T016 [US1] Update `browser/demo/server.mjs` to serve `login.html` at `/login.html` and proxy `/login/*` to the BFF at port 8000 (same pattern as existing `/enrolment/*` proxy).

**Checkpoint**: Run quickstart.md Scenario 1. `GET /login/verify` returns 200 with the correct DID.

---

## Phase 4: User Story 2 — Silent Token Refresh (Priority: P2)

**Goal**: A session token nearing expiry is silently replaced without a WebAuthn prompt.

**Independent Test**: Run quickstart.md Scenario 4 — with `SESSION_LIFETIME_SECONDS=130`, log in, wait 2 minutes, observe `POST /login/refresh` firing in DevTools Network panel with no biometric prompt.

### Implementation for User Story 2

- [X] T017 [US2] Implement `POST /login/refresh` in `bff/main.py`: accept `{"refresh_token": "..."}`. Call `session_store.consume_refresh_token(token)` — return 401 if None. Check `expires_at > now` — return 401 if expired. Call `bundle_cache.is_did_active(entry["did"])` — return 401 if False. Call `session_store.issue_session_token(did)`. Return 200 with `{"session_token", "did", "expires_at"}` matching `contracts/bff-login-api.md`.
- [X] T018 [US2] Implement `refresh()` in `browser/src/session.js`: reads `decpki_refresh` from localStorage, posts `{"refresh_token": ...}` to `POST {bffBaseUrl}/refresh`, updates `decpki_session` and `decpki_expires_at` in localStorage, re-schedules the next refresh `setTimeout`. Throws `SessionExpiredError` on BFF 401. Clears all localStorage keys and cancels the timer on `SessionExpiredError`.
- [X] T019 [US2] Ensure the `setTimeout` scheduled in `login()` (T012) calls `this.refresh()` and re-schedules itself after each successful refresh. Use `this._refreshTimer` to track the timer handle so it can be cancelled by `logout()`.

**Checkpoint**: Run quickstart.md Scenario 4. Network panel shows `POST /login/refresh` at the expected time. New `decpki_session` value in localStorage. No biometric prompt.

---

## Phase 5: User Story 3 — Explicit Logout (Priority: P3)

**Goal**: A user can log out, immediately invalidating their refresh token. Subsequent refresh attempts are rejected.

**Independent Test**: Run quickstart.md Scenario 5 — log in, note refresh token, log out, attempt manual refresh → HTTP 401.

### Implementation for User Story 3

- [X] T020 [US3] Implement `POST /login/logout` in `bff/main.py`: accept `{"refresh_token": "..."}`. Call `session_store.revoke_refresh_token(token)` (no-op if not found — idempotent). Return 200 `{"ok": true}` matching `contracts/bff-login-api.md`.
- [X] T021 [US3] Implement `logout()` in `browser/src/session.js`: posts `{"refresh_token": localStorage.getItem("decpki_refresh")}` to `POST {bffBaseUrl}/logout`, clears `decpki_session`, `decpki_refresh`, `decpki_did`, `decpki_expires_at` from localStorage, cancels `this._refreshTimer`.
- [X] T022 [US3] Wire the **Log Out** button in `browser/demo/login.html` to call `session.logout()` and update the UI to show "Logged out".

**Checkpoint**: Run quickstart.md Scenario 5. Manual `POST /login/refresh` after logout returns HTTP 401.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Tests, documentation, and hardening across all stories.

- [X] T023 [P] Write `bff/tests/test_session.py`: unit tests for `SessionStore` — `create_challenge` returns a hex string; `consume_challenge` returns None after expiry (mock `time.time`); `issue_session_token` returns a decodable JWT with correct `sub`; `verify_session_token` raises on tampered token; `issue_refresh_token` and `consume_refresh_token` round-trip; `revoke_refresh_token` causes subsequent `consume_refresh_token` to return None. Integration tests for `POST /login/start` (404 for unknown DID), `POST /login/complete` (401 on bad challenge), `GET /login/verify` (401 on expired token), `POST /login/refresh` (401 after logout), `POST /login/logout` (200 idempotent).
- [X] T024 [P] Write `browser/tests/unit/session.test.js`: unit tests for `DecPKISession` — mock `fetch` and `@simplewebauthn/browser`. Cover: `login()` stores tokens in localStorage; `LoginCancelledError` on `NotAllowedError`; `LoginFailedError` on BFF 401; `isLoggedIn()` returns false when no token; `getToken()` triggers `refresh()` when expiry within 120s; `logout()` clears localStorage and calls `POST /logout`.
- [X] T025 Update `browser/README.md` to add a **Session / Login** section documenting `DecPKISession` usage, the BFF requirement, and a link to the login demo at `/login.html`.
- [X] T026 Update the root `README.md` to add `decpki enrol-sign` / `enrol-promote` / login flow to the **How it works** section, and link to the Feature 005 quickstart.
- [X] T027 [P] Update `bff/requirements.txt` to add `python-jose[cryptography]` if not already present (verify from T001) and confirm `pip install` succeeds cleanly.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Depends on Phase 1 — blocks all user stories
- **US1 (Phase 3)**: Depends on Phase 2 — MVP deliverable; also needed by US2 and US3
- **US2 (Phase 4)**: Depends on US1 (needs `login()` and stored tokens to refresh); can run in parallel with US3 once US1 is complete
- **US3 (Phase 5)**: Depends on US1 (needs stored tokens to revoke); can run in parallel with US2
- **Polish (Phase 6)**: Depends on all desired stories complete

### User Story Dependencies

- **US1 (P1)**: Blocked only by Foundational — no story dependencies
- **US2 (P2)**: Needs US1 complete (requires `login()`, stored refresh token, and `_refreshTimer`)
- **US3 (P3)**: Needs US1 complete (requires stored refresh token from `login()`)

### Within Each User Story

- BFF endpoints before browser client (browser needs working BFF to test against)
- Core service methods before endpoint wiring
- Demo HTML after JS module is functional

### Parallel Opportunities

- T002, T003, T004 (Phase 1 skeletons) can run in parallel
- T005, T006 (Phase 2 — different files) can run in parallel after T001
- T009–T011 (BFF endpoints) and T012–T014 (browser JS) can run in parallel within Phase 3
- T023 and T024 (Phase 6 tests) can run in parallel

---

## Parallel Example: User Story 1

```bash
# BFF login endpoints and browser session module can be built in parallel:
Task: "Implement POST /login/start and /login/complete" (T009, T010)
Task: "Implement DecPKISession.login() in browser/src/session.js" (T012)

# Verification endpoint and token helpers can run alongside:
Task: "Implement GET /login/verify" (T011)
Task: "Implement getToken(), getDid(), isLoggedIn()" (T013, T014)
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (JWT + bundle cache + session store)
3. Complete Phase 3: User Story 1 (login + verify)
4. **STOP and VALIDATE**: Run quickstart.md Scenario 1
5. Demo: passkey registered in Feature 004 → log in → session token → protected endpoint

### Incremental Delivery

1. Setup + Foundational → infrastructure ready
2. US1 → login works end-to-end (MVP)
3. US2 → silent refresh added (session feels continuous)
4. US3 → logout added (complete auth lifecycle)
5. Polish → tests, docs, hardening

---

## Notes

- `[P]` tasks touch different files with no blocking dependencies within their phase
- `SESSION_SECRET` must be set as an env var — the BFF will crash on startup if missing (by design)
- The `verify_assertion` helper (T008) is the highest-risk task — WebAuthn verification data is `authenticatorData || SHA-256(clientDataJSON)`, not just the raw assertion bytes. Get this right before wiring the endpoint.
- The bundle cache background thread (T005) must use a daemon thread so it doesn't block process shutdown
- `consume_challenge` must delete the challenge on first use regardless of whether verification succeeds — prevents challenge reuse on a second attempt after a bad assertion
