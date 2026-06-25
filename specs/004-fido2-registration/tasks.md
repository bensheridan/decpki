# Tasks: FIDO2 Registration & Chain Enrolment

**Input**: Design documents from `specs/004-fido2-registration/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3)

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Create project skeletons and install dependencies before any feature work.

- [X] T001 Create `bff/` directory with `main.py`, `enrolment.py`, `cose.py`, `requirements.txt`, `tests/` as per plan.md structure
- [X] T002 Add FastAPI, uvicorn, cbor2, cryptography, httpx, pytest to `bff/requirements.txt`
- [X] T003 [P] Create `browser/src/registration.js` skeleton (empty exports: `DecPKIRegistration` class)
- [X] T004 [P] Add `@simplewebauthn/browser` to `browser/package.json` dependencies and run `npm install` in `browser/`
- [X] T005 Create `decpki/commands/enrol.py` and `decpki/commands/enrol_sign.py` skeleton files with empty command stubs
- [X] T006 Create `/tmp/decpki-enrolments/` directory and `promoted/` subdirectory (runtime storage for prototype)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Shared logic used by all three user stories — COSE decoding, request file I/O, FastAPI app bootstrap. Must complete before any story work begins.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [X] T007 Implement `bff/cose.py`: function `extract_ed25519_pubkey(attestation_object_bytes) -> bytes` that decodes the CBOR attestation object, reads `authData`, locates the COSE key map, asserts algorithm == -8, and returns the raw 32-byte public key. Raise `ValueError` with message `"Only ed25519 credentials (COSE alg -8) are accepted."` for any other algorithm.
- [X] T008 Implement `bff/enrolment.py`: `EnrolmentStore` class with methods `create(did, public_key_hex, credential_id, request_type) -> EnrolmentRequest`, `get(request_id) -> EnrolmentRequest | None`, `list_pending() -> list[EnrolmentRequest]`, `add_signature(request_id, validator_name, signature_hex) -> EnrolmentRequest`, `promote(request_id)`. Reads/writes JSON files in `/tmp/decpki-enrolments/` (path configurable via `ENROLMENT_DIR` env var). Promotes by moving file to `promoted/` subdirectory.
- [X] T009 Implement `bff/main.py`: FastAPI app with CORS enabled for localhost, lifespan startup that creates the enrolment directory, and routes imported from `enrolment.py`. Wire up `GET /`, `POST /enrolment/start`, `POST /enrolment/submit`, `GET /enrolment/{request_id}`, `GET /enrolment/` endpoints (stubs that return 501 until implemented per story).
- [X] T010 Write `bff/tests/test_cose.py`: unit tests for `extract_ed25519_pubkey` — valid ed25519 COSE key returns correct bytes; P-256 key raises ValueError with correct message; malformed CBOR raises ValueError.

**Checkpoint**: `cd bff && uvicorn main:app --port 8000` starts without error. `pytest tests/test_cose.py` passes.

---

## Phase 3: User Story 1 — New User Registration (Priority: P1) 🎯 MVP

**Goal**: A new user creates a FIDO2 credential in the browser, submits it to the BFF, and after two validators co-sign via CLI, the identity appears in the trust bundle and passes `DecPKIClient.verify()` offline.

**Independent Test**: Run quickstart.md Scenario 1 end-to-end — credential created, two validators sign, bundle regenerated, `VALID` returned offline.

### Implementation for User Story 1

- [X] T011 [US1] Implement `POST /enrolment/start` in `bff/main.py`: generate a 32-byte random challenge, assign a `pending_did` (`did:local:<uuid4>`), store the challenge in a short-lived in-memory dict keyed by `pending_did`, return the WebAuthn `PublicKeyCredentialCreationOptions` JSON matching the contract in `contracts/bff-api.md` with `pubKeyCredParams: [{"type":"public-key","alg":-8}]` and `attestation: "none"`.
- [X] T012 [US1] Implement `POST /enrolment/submit` in `bff/main.py`: decode the `clientDataJSON` (base64url → JSON, validate `type == "webauthn.create"` and `challenge` matches stored challenge), call `cose.extract_ed25519_pubkey(attestation_object_bytes)` to get the 32-byte public key, hex-encode it, call `EnrolmentStore.create()`, return 201 with the `RegistrationResult` JSON matching `contracts/bff-api.md`. Return 422 if algorithm mismatch; 409 if credential ID already exists in any stored request.
- [X] T013 [US1] Implement `GET /enrolment/{request_id}` in `bff/main.py`: call `EnrolmentStore.get()`, return 200 with status JSON or 404 if not found.
- [X] T014 [US1] Implement `GET /enrolment/` in `bff/main.py`: call `EnrolmentStore.list_pending()`, return 200 with summary array matching `contracts/bff-api.md`.
- [X] T015 [US1] Implement `decpki enrol-sign` in `decpki/commands/enrol_sign.py`: CLI sub-command accepting `--request <path>` and `--validator <key.json>`. Load the request JSON, check it is in `pending` status and not expired (`expires_at > now`). Compute the signing payload: `SHA-256(canonical_CBOR({"id": request_id, "did": did, "pubkey": public_key_hex}))` using the existing `cbor-canonical` logic. Sign with the validator's ed25519 private key. Append a `ValidatorSignature` entry to the request file. Print signature count and whether quorum is reached.
- [X] T016 [US1] Implement `decpki enrol-promote` in `decpki/commands/enrol_sign.py` (or a new `enrol_promote.py`): CLI sub-command accepting `--request <path>` and `--threshold <int>`. Verify each stored signature using the validator's public key (loaded from the identity ledger or a `--validators-dir` path). Count valid signatures; error if `< threshold`. Call the existing `decpki register` logic (or replicate it) to write an `IdentityRecord` with the enrolled `did` and `public_key_hex`. Move the request file to `promoted/`. Print the promoted DID.
- [X] T017 [US1] Wire `enrol-sign` and `enrol-promote` as sub-commands in the `decpki` CLI entry point (wherever existing commands like `keygen`, `register`, `bundle` are registered).
- [X] T018 [US1] Implement `DecPKIRegistration` in `browser/src/registration.js`: constructor validates `bffBaseUrl` (HTTPS or localhost only). `register()` method: calls `GET {bffBaseUrl}/start` → passes options to `@simplewebauthn/browser`'s `startRegistration()` → posts result to `POST {bffBaseUrl}/submit` → returns `RegistrationResult`. Map `NotAllowedError` to `RegistrationCancelledError`; map BFF 422 to `AlgorithmNotSupportedError`; map BFF 409 to `RegistrationError`.
- [X] T019 [US1] Add error classes `RegistrationCancelledError`, `AlgorithmNotSupportedError`, `RegistrationError` as named exports in `browser/src/registration.js`.
- [X] T020 [US1] Create `browser/demo/register.html`: minimal page with a **Register** button that calls `DecPKIRegistration.register()`, displays the `request_id` and `did` on success, and shows error messages on failure. Uses `textContent` (not `innerHTML`). Links to the existing verify demo page.
- [X] T021 [US1] Update `browser/demo/server.mjs` to serve `register.html` at `/register.html` and forward BFF calls (proxy `/enrolment/*` to `http://localhost:8000`) so the demo runs from a single origin (avoids CORS issues in development).

**Checkpoint**: Run quickstart.md Scenario 1 in full. `decpki verify did:local:<uuid4>` returns `VALID` after bundle regeneration. Offline verify in browser returns `VALID`.

---

## Phase 4: User Story 2 — Add Credential (Multi-Device) (Priority: P2)

**Goal**: A user with an existing registered DID can register a second device. Both credentials verify as `VALID` for the same DID.

**Independent Test**: Run quickstart.md Scenario 2 — two credentials enrolled for the same DID; both verify as `VALID`.

### Implementation for User Story 2

- [X] T022 [US2] Extend `POST /enrolment/start` in `bff/main.py` to handle the optional `?did=` query parameter: look up the DID in the promoted enrolments (or ledger), issue a 60-second nonce stored in-memory keyed by DID, and include `"request_type": "add_credential"` and `"ownership_nonce": "<base64url>"` in the response.
- [X] T023 [US2] Implement ownership proof verification in `bff/main.py`: when `POST /enrolment/submit` receives a non-null `ownership_assertion`, decode the WebAuthn assertion, verify the signature over `clientDataJSON` using the stored public key for the existing DID (loaded from promoted enrolments on disk), verify the nonce matches, and verify the nonce has not expired. Return 422 with `"Ownership proof failed."` if any check fails. Consume and delete the nonce after verification.
- [X] T024 [US2] Extend `EnrolmentStore.create()` in `bff/enrolment.py` to set `request_type = "add_credential"` and populate `existing_did` when the submission is for an existing DID.
- [X] T025 [US2] Implement `addCredential(existingDid)` in `browser/src/registration.js`: calls `GET {bffBaseUrl}/start?did=<existingDid>` to get challenge + nonce, uses `@simplewebauthn/browser`'s `startAuthentication()` to produce an assertion for the nonce, then calls `startRegistration()` for the new credential, then posts both to `POST {bffBaseUrl}/submit` with `ownership_assertion` populated. Throws `OwnershipProofFailedError` on BFF 422 with that message.
- [X] T026 [US2] Add `OwnershipProofFailedError` as a named export in `browser/src/registration.js`.
- [X] T027 [US2] Update `browser/demo/register.html` to add an **Add Credential to Existing DID** button and DID input field that invokes `addCredential()`.

**Checkpoint**: Run quickstart.md Scenario 2. Both credential DIDs return `VALID` in the browser verify demo.

---

## Phase 5: User Story 3 — Revoke a Credential (Priority: P3)

**Goal**: A specific credential can be revoked via CLI. After revocation and bundle refresh, that credential is excluded.

**Independent Test**: Run quickstart.md Scenario 3 (adapted): after revoking a credential and regenerating the bundle, `DecPKIClient.verify()` returns `NOT_FOUND` for the revoked DID entry. An unrevoked credential for the same DID (if one exists) continues to return `VALID`.

### Implementation for User Story 3

- [X] T028 [US3] Implement `decpki enrol-revoke` in `decpki/commands/enrol_sign.py` (or a new `enrol_revoke.py`): CLI sub-command accepting `--did <did>` and `--credential-id <base64url>` and `--validator <key.json>` (×N, for quorum). Loads the matching `IdentityRecord` from the ledger by DID + public key (derived from credential ID). Writes a new revocation ledger record (sets `revokedAt` timestamp). Requires the same quorum of validator signatures as enrolment. Prints confirmation.
- [X] T029 [US3] Wire `enrol-revoke` as a sub-command in the `decpki` CLI entry point.
- [X] T030 [US3] Verify that `decpki bundle` already excludes records where `revokedAt` is set (check existing bundle generation code). If not, update `decpki/bundle.py` to filter out revoked records when building the identity list for the bundle.

**Checkpoint**: After `decpki enrol-revoke` and `decpki bundle`, the revoked DID is absent from the bundle. `DecPKIClient.verify()` returns `NOT_FOUND` for that DID (or `VALID` only for unrevoked credentials).

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Validation, documentation, and hardening across all stories.

- [X] T031 [P] Write `bff/tests/test_enrolment.py`: integration tests using `httpx.AsyncClient` for the full `start → submit → get status` cycle (Scenario 1), duplicate credential rejection (Scenario 5), and expired-request rejection (Scenario 4). Use `ENROLMENT_DIR` env var to point at a temp directory.
- [X] T032 [P] Write `browser/tests/unit/registration.test.js`: unit tests for `DecPKIRegistration` — mocking `fetch` and `@simplewebauthn/browser`. Cover: successful register(), RegistrationCancelledError on NotAllowedError, AlgorithmNotSupportedError on BFF 422, RegistrationError on BFF 409, HTTPS enforcement in constructor.
- [X] T033 Update `browser/README.md` to add a **Registration** section documenting `DecPKIRegistration` usage, the BFF requirement, and a link to the demo at `/register.html`.
- [X] T034 Run all quickstart.md scenarios (1–5) manually and mark each as verified. Fix any discrepancies found.
- [X] T035 [P] Add `bff/` patterns (`__pycache__/`, `*.pyc`, `.venv/`) to the root `.gitignore` if not already covered.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Depends on Phase 1 — blocks all user stories
- **US1 (Phase 3)**: Depends on Phase 2 — MVP deliverable
- **US2 (Phase 4)**: Depends on Phase 3 (requires a promoted DID to extend); can be started in parallel with US3 once Phase 3 is complete
- **US3 (Phase 5)**: Depends on Phase 3 (requires a promoted DID to revoke); can run in parallel with US2
- **Polish (Phase 6)**: Depends on all desired stories complete

### User Story Dependencies

- **US1 (P1)**: Blocked only on Foundational — no story dependencies
- **US2 (P2)**: Needs US1 complete (promoted DID to add credential to)
- **US3 (P3)**: Needs US1 complete (promoted DID to revoke)

### Parallel Opportunities

Within Phase 1: T003 and T004 can run in parallel (both touch `browser/` but different files).
Within Phase 3: T011–T014 (BFF endpoints) and T018–T019 (JS client) can be developed in parallel once T007–T009 are complete.
Within Phase 6: T031 and T032 can run in parallel (different test files).

---

## Parallel Example: User Story 1

```bash
# BFF endpoints and JS client can be built in parallel:
Task: "Implement POST /enrolment/start" (T011)
Task: "Implement DecPKIRegistration.register()" (T018)

# CLI tools can be built in parallel with both:
Task: "Implement decpki enrol-sign" (T015)
Task: "Implement decpki enrol-promote" (T016)
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational
3. Complete Phase 3: User Story 1 (T011–T021)
4. **STOP and VALIDATE**: Run quickstart.md Scenario 1 end-to-end
5. Demo: new user registers passkey → validators co-sign → bundle generated → browser verifies offline

### Incremental Delivery

1. Setup + Foundational → BFF starts, COSE decoding works
2. US1 → Full new-user enrolment pipeline (MVP)
3. US2 → Multi-device support added
4. US3 → Revocation added
5. Polish → Tests, docs, hardening

---

## Notes

- `[P]` tasks touch different files and have no blocking dependencies within their phase
- Each user story phase is independently testable — stop at any checkpoint to demo
- The existing `DecPKIClient.verify()` API and bundle format are unchanged; no regression risk
- The COSE key extraction in T007 is the highest-risk implementation task — the attestation object format varies slightly by authenticator. Use a real device or the `@simplewebauthn/testing` fixtures to validate.
- ed25519 COSE algorithm identifier is `-8` (integer, not string). WebAuthn spec uses IANA COSE Algorithms registry.
