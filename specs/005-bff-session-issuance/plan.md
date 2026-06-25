# Implementation Plan: BFF Session Issuance

**Branch**: `005-bff-session-issuance` | **Date**: 2026-06-25 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/005-bff-session-issuance/spec.md`

## Summary

Extend the Feature 004 BFF to add a complete login flow: browser presents a WebAuthn assertion, the BFF verifies it against the enrolled credential public key and the current trust bundle, and issues a short-lived session token plus a longer-lived refresh token. Adds silent token refresh and explicit logout. A new `DecPKISession` browser module handles the client-side login, token storage, and refresh scheduling.

## Technical Context

**Language/Version**: Python 3.11 (BFF extension), JavaScript ES2022 (browser session module) — same as Features 003 & 004.

**Primary Dependencies**:
- BFF: `python-jose[cryptography]` (JWT signing/verification with HS256); existing `cbor2`, `cryptography`, `fastapi` already present.
- Browser: `@simplewebauthn/browser` (already added in Feature 004 for assertion); no new JS dependencies.

**Storage**: Login challenges and refresh tokens stored in-memory (Python dicts in BFF process). Session tokens are self-contained (no server lookup needed for verification). Promoted enrolments read from `/tmp/decpki-enrolments/promoted/` (established in Feature 004).

**Testing**: pytest + FastAPI TestClient (BFF), Vitest (browser).

**Target Platform**: Same as Feature 004 — Linux/macOS BFF, any FIDO2-capable browser.

**Project Type**: Extension of existing BFF service + new browser JS module.

**Performance Goals**: Login round-trip (challenge + assertion + token response) < 3 seconds. Token refresh < 500ms (no WebAuthn prompt).

**Constraints**: Session tokens are BFF-internal (not chain-recorded). Trust bundle re-checked on every refresh. HTTPS required in production; localhost exempted for demo.

**Scale/Scope**: Single-user prototype demo; in-memory token store is acceptable.

## Constitution Check

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Decentralised Trust | PASS | Login gated on DID presence in the validator-signed trust bundle. No single CA. |
| II. Offline-First Verification | PASS | Login is online by definition. Existing offline verify path unchanged. |
| III. Cryptographic Auditability | PASS | Session tokens are ephemeral BFF state — not identity records. No ledger mutation. |
| IV. Minimal Credential Surface | PASS | No new credential types. Login reuses the ed25519 credential from enrolment. JWT HS256 for BFF-internal sessions only. |
| V. Explicit Revocation Policy | PASS | Bundle re-checked on every token refresh; revoked DID denied within one bundle refresh cycle. |
| VI. Validator Quorum Governance | PASS | No new chain writes. Login relies on the existing quorum-signed bundle. |

No violations — Complexity Tracking not required.

## Project Structure

### Documentation (this feature)

```text
specs/005-bff-session-issuance/
├── plan.md              ← this file
├── research.md          ← Phase 0 output
├── data-model.md        ← Phase 1 output
├── quickstart.md        ← Phase 1 output
├── contracts/           ← Phase 1 output
│   ├── bff-login-api.md
│   └── browser-session-api.md
└── tasks.md             ← Phase 2 output (/speckit-tasks)
```

### Source Code (repository root)

```text
bff/                          ← existing (extended)
├── main.py                   ← add /login/* route imports
├── session.py                ← new: JWT issue/verify, refresh token store, login challenge store
├── bundle_cache.py           ← new: BFF-side bundle loader and DID lookup
└── tests/
    └── test_session.py       ← new

browser/                      ← existing (extended)
├── src/
│   └── session.js            ← new: DecPKISession class
└── tests/
    └── unit/
        └── session.test.js   ← new
```

**Structure Decision**: Extend the existing `bff/` and `browser/` directories. `session.py` keeps JWT logic isolated from enrolment logic in `enrolment.py`. `bundle_cache.py` makes the bundle-loading logic reusable and independently testable.
