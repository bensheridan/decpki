# Implementation Plan: Protected Resource Demo

**Branch**: `006-protected-resource-demo` | **Date**: 2026-06-25 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/006-protected-resource-demo/spec.md`

## Summary

Add a `GET /api/me` endpoint to the BFF that validates the session JWT and returns the authenticated user's DID and session details. Update `login.html`'s **Call Protected Endpoint** button to call this endpoint instead of the raw token-verification utility. The result is a complete, narrable demo: register → log in → access protected data → log out.

## Technical Context

**Language/Version**: Python 3.11 (BFF extension), JavaScript ES2022 (browser update) — same as Features 004 & 005.

**Primary Dependencies**: Existing `python-jose[cryptography]`, `fastapi`. No new dependencies.

**Storage**: None. `GET /api/me` decodes the self-contained JWT without a store lookup.

**Testing**: pytest + FastAPI TestClient (BFF), Vitest (browser — update existing `session.test.js` if needed).

**Target Platform**: Same as Feature 005 — Linux/macOS BFF, any FIDO2-capable desktop browser.

**Project Type**: Extension of existing BFF service + update to browser demo HTML.

**Performance Goals**: `/api/me` response < 100ms (pure JWT decode, no I/O).

**Constraints**: JWT verified with existing `SESSION_SECRET`. The endpoint does not re-check the trust bundle — token validity is sufficient (revocation lag is a known documented trade-off from Feature 005 research). HTTPS required in production; localhost exempted.

**Scale/Scope**: Single-user prototype demo.

## Constitution Check

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Decentralised Trust | PASS | No new trust anchor. JWT was issued after a trust-bundle-backed login. |
| II. Offline-First Verification | PASS | No change to offline verify path. |
| III. Cryptographic Auditability | PASS | No new ledger writes. Session tokens are ephemeral BFF state. |
| IV. Minimal Credential Surface | PASS | No new credential type. Reuses the ed25519-backed JWT from Feature 005. |
| V. Explicit Revocation Policy | PASS | Revocation lag documented in Feature 005 research and accepted as prototype trade-off. |
| VI. Validator Quorum Governance | PASS | No new chain writes. |

No violations — Complexity Tracking not required.

## Project Structure

### Documentation (this feature)

```text
specs/006-protected-resource-demo/
├── plan.md              ← this file
├── research.md          ← Phase 0 output
├── contracts/
│   └── bff-api.md       ← GET /api/me endpoint contract
├── quickstart.md        ← Phase 1 output
└── tasks.md             ← Phase 2 output (/speckit-tasks)
```

### Source Code (repository root)

```text
bff/                          ← existing (extended)
├── main.py                   ← add GET /api/me route
└── tests/
    └── test_api_me.py        ← new: tests for /api/me

browser/                      ← existing (updated)
└── demo/
    └── login.html            ← update "Call Protected Endpoint" to call /api/me
```

**Structure Decision**: Minimal extension — one new BFF endpoint, one updated HTML file, one new test file. No new modules required; `GET /api/me` reuses `_session_store.verify_session_token()` from Feature 005.
