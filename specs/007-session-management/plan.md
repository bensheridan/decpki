# Implementation Plan: Session Management

**Branch**: `007-session-management` | **Date**: 2026-06-25 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/007-session-management/spec.md`

## Summary

Extend the BFF's in-memory session store to support DID-indexed lookup and per-session revocation. Add three new BFF endpoints (`GET /api/sessions`, `DELETE /api/sessions/{id}`) and a new `sessions.html` demo page with session list, per-session revoke buttons, and an **Add New Device** button that re-enters the Feature 004 `addCredential` enrolment flow. The critical design challenge is enabling immediate post-revocation rejection (SC-002) while still using self-contained JWTs — solved by a lightweight server-side session registry that maps session IDs to validity state.

## Technical Context

**Language/Version**: Python 3.11 (BFF extension), JavaScript ES2022 (browser) — same as Features 004–006.

**Primary Dependencies**: Existing `python-jose[cryptography]`, `fastapi`, `@simplewebauthn/browser` (for Add New Device). No new dependencies.

**Storage**: In-memory Python dicts in the BFF process. The existing `_refresh_tokens` dict (keyed by token hex) is extended to support DID-indexed lookup. A separate `_session_registry` dict maps `jti` (JWT unique ID) → validity flag, enabling immediate revocation of session tokens before expiry.

**Testing**: pytest + FastAPI TestClient (BFF), Vitest (browser).

**Target Platform**: Same as Feature 006 — Linux/macOS BFF, desktop browser.

**Project Type**: Extension of existing BFF + new browser demo page.

**Performance Goals**: Session list response < 200ms (pure memory scan). Revocation < 100ms.

**Constraints**:
- Immediate revocation (SC-002) requires a server-side `jti` blocklist — the self-contained JWT cannot be invalidated without it. The blocklist is in-memory (lost on restart, accepted prototype limitation).
- The `jti` blocklist must be checked in `GET /api/me` and `GET /login/verify` as well as the new session endpoints.
- The "Add New Device" flow reuses `DecPKIRegistration.addCredential()` from Feature 004 — no new enrolment logic.
- Session IDs exposed in the list API are refresh token identifiers (truncated to a safe prefix for display), not raw tokens — the full token is never sent back to a different client.

**Scale/Scope**: Single-user prototype demo. In-memory session registry holds at most a handful of entries.

## Constitution Check

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Decentralised Trust | PASS | No new trust anchor. Sessions are still gated on the trust-bundle-backed login from Feature 005. |
| II. Offline-First Verification | PASS | No change to offline verify path. |
| III. Cryptographic Auditability | PASS | No new ledger writes. Session registry is ephemeral BFF state. |
| IV. Minimal Credential Surface | PASS | No new credential type. The `jti` blocklist is BFF-internal state. |
| V. Explicit Revocation Policy | PASS | Session revocation is immediate (blocklist checked on every protected request). Revocation lag documented: BFF restart clears the blocklist — accepted prototype limitation. |
| VI. Validator Quorum Governance | PASS | No new chain writes. Add New Device reuses the existing Feature 004 quorum-gated enrolment flow. |

No violations — Complexity Tracking not required.

## Project Structure

### Documentation (this feature)

```text
specs/007-session-management/
├── plan.md              ← this file
├── research.md          ← Phase 0 output
├── data-model.md        ← Phase 1 output
├── contracts/
│   ├── bff-sessions-api.md      ← GET /api/sessions, DELETE /api/sessions/{id}
│   └── browser-sessions-api.md  ← DecPKISessions class contract
├── quickstart.md        ← Phase 1 output
└── tasks.md             ← Phase 2 output (/speckit-tasks)
```

### Source Code (repository root)

```text
bff/                          ← existing (extended)
├── main.py                   ← add GET/DELETE /api/sessions routes; add jti blocklist check to /api/me and /login/verify
├── session.py                ← extend SessionStore: jti blocklist, DID-indexed session lookup, per-session revoke
└── tests/
    └── test_sessions.py      ← new: tests for session list and revocation endpoints

browser/                      ← existing (extended)
├── src/
│   └── sessions.js           ← new: DecPKISessions class (list, revoke, addDevice)
├── demo/
│   ├── sessions.html         ← new: session management demo page
│   └── server.mjs            ← add /api/* proxy (already done in Feature 006); add sessions.html route
└── tests/
    └── unit/
        └── sessions.test.js  ← new: unit tests for DecPKISessions
```

**Structure Decision**: Extend `bff/session.py` and `bff/main.py`; new browser module `sessions.js` keeps session management logic separate from login logic (`session.js`). New demo page `sessions.html` is linked from `login.html`.
