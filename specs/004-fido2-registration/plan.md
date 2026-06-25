# Implementation Plan: FIDO2 Registration & Chain Enrolment

**Branch**: `004-fido2-registration` | **Date**: 2026-06-25 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/004-fido2-registration/spec.md`

## Summary

Extend the decentralised PKI prototype to allow users to create FIDO2 credentials (passkeys) in the browser and enrol the resulting ed25519 public key into the trust chain via a BFF submission + validator co-signing pipeline. Once enrolled, the identity appears in the next trust bundle and can be verified by the existing `DecPKIClient.verify()` API without modification.

## Technical Context

**Language/Version**: Python 3.11 (BFF + validator extension), JavaScript ES2022 (browser registration client) — matches existing codebase languages.

**Primary Dependencies**:
- Browser: `@simplewebauthn/browser` (WebAuthn abstraction, handles cross-browser quirks); existing `decpki-client` library unchanged.
- BFF: FastAPI (Python HTTP server); `cbor2` (COSE key decoding, already used by decpki); `cryptography` (ed25519 public key validation).
- Validator CLI: existing `decpki` Python package extended with `enrol` and `enrol-sign` sub-commands.

**Storage**: Enrolment requests stored as JSON files on disk under `/tmp/enrolments/` (prototype — matches the file-based approach of the existing CLI demo). Production would use a database.

**Testing**: pytest (Python BFF + CLI), Vitest (browser JS).

**Target Platform**: Linux/macOS server for BFF + validator CLI; any FIDO2-capable browser for the registration flow.

**Project Type**: Browser extension to existing JS library + new Python BFF service + Python CLI extension.

**Performance Goals**: Registration round-trip (browser → BFF → disk) completes in < 2 seconds. Validator co-signing via CLI is manual in this prototype (no latency requirement).

**Constraints**: ed25519 only (COSE algorithm -8); HTTPS required for WebAuthn in production (localhost exempted for dev); private key never transmitted; existing bundle format and `verify()` API unchanged.

**Scale/Scope**: Single-user demo scale; the goal is to prove the enrolment pipeline end-to-end.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Decentralised Trust (N-of-M validator quorum) | PASS | Enrolment requires 2-of-3 validator co-signatures before identity is promoted. |
| II. Offline-First Verification | PASS | `DecPKIClient.verify()` is unchanged; enrolled identities enter the bundle and verify offline. Registration itself is online-only (by definition — you need to submit a key). |
| III. Cryptographic Auditability | PASS | Enrolment requests and their signatures are written as immutable ledger records; revocation is a new record. |
| IV. Minimal Credential Surface | PASS | Only ed25519 (COSE alg -8) credentials are accepted. P-256 / RSA are rejected at the BFF. W3C DID format preserved. |
| V. Explicit Revocation Policy | PASS | Revocation uses the existing bundle-expiry model (Option B). Revocation lag = bundle validity window, same as Feature 003. |
| VI. Validator Quorum Governance | PASS | Minimum 2-of-3; quorum parameters passed as CLI flags, matching existing `decpki bundle` pattern. |

No violations — Complexity Tracking section not required.

## Project Structure

### Documentation (this feature)

```text
specs/004-fido2-registration/
├── plan.md              ← this file
├── research.md          ← Phase 0 output
├── data-model.md        ← Phase 1 output
├── quickstart.md        ← Phase 1 output
├── contracts/           ← Phase 1 output
│   ├── bff-api.md
│   └── browser-registration-api.md
└── tasks.md             ← Phase 2 output (/speckit-tasks)
```

### Source Code (repository root)

```text
bff/                          ← new: Python BFF service
├── main.py                   ← FastAPI app (enrolment endpoints)
├── enrolment.py              ← enrolment request logic
├── cose.py                   ← COSE key decoding (ed25519 only)
├── requirements.txt
└── tests/
    ├── test_enrolment.py
    └── test_cose.py

decpki/                       ← existing Python package (extended)
└── commands/
    ├── enrol.py              ← new: `decpki enrol` sub-command (submit pending request)
    └── enrol_sign.py         ← new: `decpki enrol-sign` sub-command (validator co-signing)

browser/                      ← existing JS library (extended)
├── src/
│   └── registration.js       ← new: WebAuthn credential creation + BFF submission
└── tests/
    └── unit/
        └── registration.test.js
```

**Structure Decision**: Two-project extension (existing `decpki` package + new `bff/` service) plus a new JS module alongside the existing `browser/` library. No new top-level project structure invented; all additions are coherent with existing patterns.
