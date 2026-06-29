# Tasks: BFF Persistent Storage

**Input**: Design documents from `specs/008-bff-persistent-storage/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/session-store.md

**Organization**: Tasks grouped by user story; all build on the shared `SqliteSessionStore` foundation.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[US#]**: User story this task belongs to

---

## Phase 1: Setup

**Purpose**: No new files or packages needed — stdlib `sqlite3` and `threading` are already
available. This phase only pins the environment and verifies the test harness can run.

- [X] T001 Verify `bff/requirements.txt` needs no changes (sqlite3 is stdlib) — read `bff/requirements.txt` and confirm no additions required

---

## Phase 2: Foundational — SqliteSessionStore Core

**Purpose**: Implement the SQLite-backed `SqliteSessionStore` class in `bff/session.py`. This is the
single prerequisite that all three user stories depend on. No story-specific endpoints or logic
is included here — only the drop-in replacement for `SessionStore`.

**⚠️ CRITICAL**: All user story tasks depend on this phase completing first.

- [X] T002 Add `import sqlite3, threading` to the imports block at the top of `bff/session.py`
- [X] T003 Add `SqliteSessionStore` class to `bff/session.py` with `__init__` that opens the SQLite connection (WAL mode), creates the lock, calls `_init_schema()` and `_prune_expired()`; add `close()` method
- [X] T004 Implement `_init_schema()` in `SqliteSessionStore` in `bff/session.py`: CREATE TABLE IF NOT EXISTS for `challenges`, `refresh_tokens` (with index on `did`), and `jti_blocklist` per the schema in `plan.md`
- [X] T005 Implement `_prune_expired()` in `SqliteSessionStore` in `bff/session.py`: DELETE expired rows from all three tables using `now = int(time.time())`
- [X] T006 Implement `create_challenge` and `consume_challenge` in `SqliteSessionStore` in `bff/session.py` — INSERT challenge row; SELECT+DELETE on consume, return None if absent or expired
- [X] T007 Implement `issue_refresh_token`, `consume_refresh_token`, and `revoke_refresh_token` in `SqliteSessionStore` in `bff/session.py` — INSERT token row; SELECT without delete on consume; DELETE + remove from did-index on revoke
- [X] T008 Implement `issue_session_token` in `SqliteSessionStore` in `bff/session.py` — same JWT minting logic as `SessionStore`; UPDATE `last_jti` in `refresh_tokens` when `refresh_token_hex` provided
- [X] T009 Implement `verify_session_token` in `SqliteSessionStore` in `bff/session.py` — delegate to `jwt.decode` (identical to `SessionStore`)
- [X] T010 Implement `is_jti_revoked` in `SqliteSessionStore` in `bff/session.py` — SELECT from `jti_blocklist` WHERE `jti = ? AND original_exp > now`
- [X] T011 Implement `list_sessions` in `SqliteSessionStore` in `bff/session.py` — SELECT from `refresh_tokens` WHERE `did = ? AND expires_at > now`, return list of dicts with `session_id = token_hex[:16]`
- [X] T012 Implement `revoke_session` in `SqliteSessionStore` in `bff/session.py` — find token by 16-char prefix, INSERT into `jti_blocklist` (with `original_exp = now + SESSION_LIFETIME_SECONDS`), call `revoke_refresh_token`, return `(True, token_hex)`
- [X] T013 Wire `SqliteSessionStore` into `bff/main.py`: change `from session import SessionStore` to also import `SqliteSessionStore`; replace `_session_store = SessionStore()` with `_session_store = SqliteSessionStore()` at module level (or inside the lifespan handler if that's where it currently lives)

**Checkpoint**: BFF starts, creates `/tmp/decpki-bff.db`, and all existing endpoints work.
Verify by running `uvicorn main:app` and checking that no import errors appear.

---

## Phase 3: User Story 1 — Sessions Survive Restart (Priority: P1) 🎯 MVP

**Goal**: A session established before a BFF restart remains usable after restart without re-login.

**Independent Test**: Register → login → capture refresh token → restart BFF → `POST /login/refresh` succeeds → `GET /api/me` returns 200.

- [X] T014 [US1] Update `bff/tests/test_sessions.py`: change the `store` fixture from `SessionStore()` to `SqliteSessionStore(path=":memory:")` and add `store.close()` in teardown; ensure all existing tests pass
- [X] T015 [US1] Add `test_refresh_token_survives_restart` to `bff/tests/test_sessions_persist.py` (new file): create `SqliteSessionStore(path=tmp_path/"bff.db")`, issue refresh token, close, reopen same path, assert `consume_refresh_token` returns the original entry
- [X] T016 [US1] Add `test_session_token_refresh_after_restart` to `bff/tests/test_sessions_persist.py`: issue refresh token in first store instance, close, reopen, call `issue_session_token` with the refresh token hex, assert non-None JWT returned

**Checkpoint**: `pytest bff/tests/test_sessions.py bff/tests/test_sessions_persist.py` passes. US1 is independently verified.

---

## Phase 4: User Story 2 — Revocations Are Durable (Priority: P2)

**Goal**: Revoked sessions remain invalid after BFF restart.

**Independent Test**: Login → revoke via `DELETE /api/sessions/{id}` → restart BFF → session token returns 401.

- [X] T017 [US2] Add `test_revocation_survives_restart` to `bff/tests/test_sessions_persist.py`: issue refresh token + session token in first store instance, call `revoke_session`, close, reopen same path, assert `is_jti_revoked(jti)` returns True
- [X] T018 [US2] Add `test_other_sessions_unaffected_after_revoke_restart` to `bff/tests/test_sessions_persist.py`: issue two refresh tokens for the same DID, revoke one, close+reopen, assert revoked JTI is still blocked and the other refresh token is still consumable

**Checkpoint**: `pytest bff/tests/test_sessions_persist.py` passes including both US1 and US2 tests. Revocation durability confirmed.

---

## Phase 5: User Story 3 — Challenge Expiry Respected After Restart (Priority: P3)

**Goal**: Unexpired login challenges survive restarts; expired ones are rejected.

**Independent Test**: Create challenge → restart BFF within TTL → submit assertion → succeeds. Create expired challenge → restart → submit → 400.

- [X] T019 [US3] Add `test_valid_challenge_survives_restart` to `bff/tests/test_sessions_persist.py`: create challenge in first store, close, reopen, assert `consume_challenge` returns the entry (not None) while TTL window is open
- [X] T020 [US3] Add `test_expired_challenge_rejected_after_restart` to `bff/tests/test_sessions_persist.py`: create challenge with `expires_at` already in the past (patch `time.time` or insert row directly), close, reopen, assert `consume_challenge` returns None

**Checkpoint**: All persist tests pass. All three user stories are independently validated.

---

## Phase 6: Polish & Cross-Cutting Concerns

- [X] T021 [P] Add `BFF_STORE_PATH` env var documentation to `bff/README.md` or top of `bff/main.py` docstring: document default `/tmp/decpki-bff.db` and `:memory:` option for tests
- [X] T022 Add startup log line to `bff/main.py` lifespan or `SqliteSessionStore.__init__` that prints the store path (e.g. `[session-store] using SQLite at /tmp/decpki-bff.db`)
- [X] T023 [P] Add `test_corrupt_store_falls_back_gracefully` to `bff/tests/test_sessions_persist.py`: write a non-SQLite file to the store path, attempt `SqliteSessionStore(path=...)`, assert it raises a clear error or starts with empty state (document whichever behaviour is implemented)
- [X] T024 Run full BFF test suite `pytest bff/tests/ -v` and confirm all pass

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Depends on Phase 1 — BLOCKS all user stories
- **US1 (Phase 3)**: Depends on Phase 2 (T002–T013)
- **US2 (Phase 4)**: Depends on Phase 2; can start in parallel with US1 once T012 is done
- **US3 (Phase 5)**: Depends on Phase 2; can start in parallel with US1/US2 once T005–T006 are done
- **Polish (Phase 6)**: Depends on all user stories complete

### Within Phase 2 (sequential — single file)

T002 → T003 → T004 → T005 → T006 → T007 → T008 → T009 → T010 → T011 → T012 → T013

All are in `bff/session.py` and `bff/main.py`; must be sequential to avoid merge conflicts.

### Parallel Opportunities

- T015, T016 within US1 can run in parallel (different test functions, same file)
- T017, T018 within US2 can run in parallel
- T019, T020 within US3 can run in parallel
- T021, T023 in Polish are independent

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1 (T001)
2. Complete Phase 2 (T002–T013) — the entire `SqliteSessionStore` implementation
3. Complete Phase 3 (T014–T016) — session persistence tests
4. **STOP AND VALIDATE**: run `pytest bff/tests/` and do a manual restart test
5. Sessions now survive restarts — ship this as the MVP

### Incremental Delivery

- US1 (Phase 3) → confirms restart safety for active sessions
- US2 (Phase 4) → adds revocation durability
- US3 (Phase 5) → adds challenge durability (low-priority edge case)
- Polish (Phase 6) → observability and hardening

---

## Notes

- All SQLite writes use `with self._conn:` (auto-commit transaction) inside `self._lock`
- The `SessionStore` class is kept in `bff/session.py` unchanged — it may still be useful for
  unit tests that don't want to depend on SQLite at all, or for reference
- `check_same_thread=False` is required because FastAPI runs handlers in a thread pool
- `:memory:` SQLite mode gives full test isolation with zero disk I/O — use it in all fixtures
  except the cross-restart persistence tests (which must use a real file path)
