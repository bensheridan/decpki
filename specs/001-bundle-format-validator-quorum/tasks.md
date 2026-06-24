---
description: "Task list for Bundle Format & 3-Node Validator Quorum Prototype"
---

# Tasks: Bundle Format & 3-Node Validator Quorum Prototype

**Input**: Design documents from `specs/001-bundle-format-validator-quorum/`

**Prerequisites**: plan.md ✅, spec.md ✅, research.md ✅, data-model.md ✅, contracts/ ✅, quickstart.md ✅

**Tests**: Not explicitly requested — test tasks are included only for the contract-verification
scenarios (all five verify outcomes) as they are in the acceptance criteria.

**Organization**: Tasks grouped by user story for independent implementation and testing.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Parallelizable (different files, no shared dependencies)
- **[Story]**: User story this task belongs to (US1, US2, US3)

---

## Phase 1: Setup

**Purpose**: Project initialization and package structure

- [x] T001 Initialize Python package at repo root: create `pyproject.toml` with `[project]`, `[project.scripts]` (`decpki = "cli.decpki_cli:cli"`), and `[tool.pytest.ini_options]` sections; list dependencies `cbor2`, `cryptography`, `click`
- [x] T002 Create directory skeleton: `src/decpki/`, `cli/`, `tests/unit/`, `tests/integration/`, `tests/contract/` with `__init__.py` files in each Python package
- [x] T003 [P] Add `.gitignore` entries for `*.key.json`, `*.cbor`, `__pycache__/`, `.pytest_cache/`, `dist/`
- [x] T004 [P] Create `tests/conftest.py` with shared pytest fixtures: `tmp_identity_log` (empty IdentityLog in temp dir), `three_validators` (three ValidatorNode instances with generated keys)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core data structures and cryptographic primitives — MUST complete before any user story

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [x] T005 Implement `src/decpki/models.py`: dataclasses `IdentityRecord`, `ValidatorSignature`, `MerkleProof`, `TrustBundle` (with embedded `IdentityEntry`), and `ValidatorNode` (with `from_key_file()` classmethod and `sign(data: bytes) -> bytes` method using `Ed25519PrivateKey`); include `IdentityLog` class with `load()`, `empty()`, `save()`, `add()`, `get()`, `active_records()` methods; raise `DuplicateDIDError` on duplicate `add()`
- [x] T006 [P] Implement `src/decpki/merkle.py`: `build_tree(leaves: list[bytes]) -> list[list[bytes]]` builds a binary SHA-256 Merkle tree (leaf hash = `SHA256(0x00 + data)`, node hash = `SHA256(0x01 + left + right)`); `get_root(tree) -> bytes`; `get_proof(tree, index: int) -> list[dict]` returns list of `{"h": bytes, "s": "left"|"right"}`; `verify_proof(leaf_hash: bytes, proof: list[dict], root: bytes) -> bool` walks sibling list
- [x] T007 [P] Implement `src/decpki/exceptions.py`: `DecPKIError(Exception)`, `QuorumError(DecPKIError)` with `.required` and `.provided` int fields, `DuplicateDIDError(DecPKIError)` with `.did` field, `BundleDecodeError(DecPKIError)` with `.reason` field
- [x] T008 Implement CBOR canonical serialisation helpers in `src/decpki/bundle.py`: `serialise_record(record: IdentityRecord) -> bytes` (CBOR map with short field names per data-model.md wire format); `serialise_bundle_for_signing(bundle: TrustBundle) -> bytes` (full bundle CBOR with `signatures=[]`); `deserialise_bundle(raw: bytes) -> TrustBundle` (inverse; raises `BundleDecodeError` on malformed input or unknown `fmt_ver`)

**Checkpoint**: Core data structures, Merkle tree, and CBOR serialisation complete

---

## Phase 3: User Story 1 — Generate and Verify a Trust Bundle (Priority: P1) 🎯 MVP

**Goal**: Register an identity in the quorum, generate a signed CBOR bundle, verify the identity offline with zero network calls

**Independent Test**: Run `decpki keygen`, `decpki register`, `decpki bundle`, then `decpki verify` with no network access — exit code 0, output contains "VALID"

### Implementation for User Story 1

- [x] T009 [P] [US1] Implement `register_identity()` in `src/decpki/quorum.py`: accepts `IdentityLog`, `IdentityRecord` (partial), `list[ValidatorNode]`, `threshold: int`; sets `issued_at` (auto-increment block counter from log), `issued_by` (validator DIDs); raises `QuorumError` if `len(validators) < threshold`; raises `DuplicateDIDError` if DID already in log; appends completed record and saves log; returns completed `IdentityRecord`
- [x] T010 [US1] Implement `generate_bundle()` in `src/decpki/bundle.py`: accepts `IdentityLog`, `list[ValidatorNode]`, `threshold: int`, `grace_seconds: int`; builds Merkle tree over all `active_records()` sorted by DID; computes root; generates `MerkleProof` per record; sets `issued_at = int(time.time())`, `expires_at = issued_at + grace_seconds`; calls `serialise_bundle_for_signing()` then `node.sign()` for each validator; raises `QuorumError` if `len(validators) < threshold`; returns raw CBOR bytes
- [x] T011 [US1] Implement `verify()` in `src/decpki/verify.py`: accepts `bundle_path: str | Path`, `did: str`; deserialises bundle; checks `format_version == 1`; checks `len(signatures) >= threshold` → `QUORUM_FAILURE`; verifies each `ValidatorSignature.signature` against `validator_pubkey` and canonical bundle bytes → `TAMPERED`; checks `expires_at > time.time()` → `EXPIRED`; recomputes Merkle root from all identity records → `INVALID` if mismatch; looks up DID → `NOT_FOUND`; verifies inclusion proof for the DID's record → `INVALID`; returns `VerifyResult` with `outcome=VALID`
- [x] T012 [US1] Implement `Outcome` enum and `VerifyResult` dataclass in `src/decpki/verify.py` per python-api-contract.md
- [x] T013 [US1] Wire public API in `src/decpki/__init__.py`: export `verify`, `generate_bundle`, `register_identity`, `IdentityRecord`, `ValidatorNode`, `IdentityLog`, `Outcome`, `VerifyResult`
- [x] T014 [US1] Implement `decpki keygen` CLI command in `cli/decpki_cli.py`: `--name`, `--out`; calls `Ed25519PrivateKey.generate()`; writes key file (JSON, mode 0600); prints DID, pubkey hex, filename; exit 1 if file exists without `--force`
- [x] T015 [US1] Implement `decpki register` CLI command: `--did`, `--pubkey`, `--validator` (multiple), `--meta`, `--valid-until-block`; loads validators via `ValidatorNode.from_key_file()`; calls `register_identity()`; prints confirmation; exit 2 on `DuplicateDIDError`, exit 3 on `QuorumError`
- [x] T016 [US1] Implement `decpki bundle` CLI command: `--validator` (multiple), `--threshold`, `--grace` (parse `24h`/`7d`/`3600s` to seconds), `--out`; calls `generate_bundle()`; writes CBOR to file; prints summary; exit 3 on `QuorumError`
- [x] T017 [US1] Implement `decpki verify` CLI command: `--bundle`, `--did`; calls `verify()`; prints result message; exits with the appropriate code (0/4/5/6/7/8) per cli-contract.md
- [x] T018 [US1] Implement `decpki inspect` CLI command: `--bundle`; deserialises bundle; prints human-readable summary including remaining validity time; exit 9 on `BundleDecodeError`
- [x] T019 [US1] Add integration test `tests/integration/test_e2e_verify.py`: using `three_validators` fixture, register one identity, call `generate_bundle()`, write bundle to temp file, call `verify()` — assert `outcome == VALID`; also assert `verify()` for an unknown DID returns `NOT_FOUND`

**Checkpoint**: Full offline verification flow works end-to-end. Run quickstart.md Steps 1–4.

---

## Phase 4: User Story 2 — Bundle Signing Requires Quorum (Priority: P2)

**Goal**: Client rejects bundles with fewer signatures than threshold; accepts bundles at threshold

**Independent Test**: 1-sig bundle → `QUORUM_FAILURE` (exit 8); 2-sig bundle → `VALID` (exit 0)

### Implementation for User Story 2

- [x] T020 [US2] Add contract test `tests/contract/test_quorum.py`: (a) generate bundle with only 1 validator where threshold=2 — assert `QuorumError` is raised OR if bundle is manually constructed with 1 sig, `verify()` returns `QUORUM_FAILURE`; (b) generate bundle with 2 validators where threshold=2 — assert `verify()` returns `VALID` (US2 acceptance scenarios)
- [x] T021 [US2] Verify that `generate_bundle()` raises `QuorumError` when `len(validators) < threshold` — this is already implemented in T010; add explicit unit test in `tests/unit/test_bundle.py` covering the `QuorumError` path
- [x] T022 [US2] Add helper `_make_bundle_with_n_sigs(n)` to `tests/contract/test_quorum.py` that constructs a `TrustBundle` with exactly `n` signatures (using CBOR serialisation directly) for testing client-side quorum check independently of `generate_bundle()`

**Checkpoint**: `decpki bundle --validator alpha.key.json --threshold 2` raises error. 2-sig bundle verifies.

---

## Phase 5: User Story 3 — Bundle Expiry Enforces Offline Grace Window (Priority: P3)

**Goal**: Expired bundles are rejected; non-expired bundles pass

**Independent Test**: Generate bundle with 2s grace, wait 3s, verify → `EXPIRED` (exit 5); fresh bundle verifies normally

### Implementation for User Story 3

- [x] T023 [US3] Add contract test `tests/contract/test_expiry.py`: (a) generate bundle with `grace_seconds=1`, sleep 2s, call `verify()` — assert `EXPIRED`; (b) generate bundle with `grace_seconds=3600`, call `verify()` immediately — assert `VALID` (US3 acceptance scenarios)
- [x] T024 [US3] Implement `_parse_grace(value: str) -> int` helper in `cli/decpki_cli.py`: parses `24h` → 86400, `7d` → 604800, `3600s` → 3600; raises `click.BadParameter` for unknown format; add unit test in `tests/unit/test_cli_helpers.py`

**Checkpoint**: `decpki bundle --grace 2s` produces expiring bundle. Quickstart Scenario C passes.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Tamper detection, edge cases, and quickstart validation

- [x] T025 [P] Add contract test `tests/contract/test_tamper.py`: load a valid bundle file, flip one byte at offset 100, write to new file, call `verify()` — assert `TAMPERED` (exit 6); covers Quickstart Scenario D
- [x] T026 [P] Add unit tests `tests/unit/test_merkle.py`: test `verify_proof()` with a known 4-leaf tree (manually computed expected root); test empty tree (single-identity bundle); test odd-leaf-count tree (3 identities — tree must duplicate last leaf)
- [x] T027 [P] Add unit tests `tests/unit/test_models.py`: `IdentityLog.add()` raises `DuplicateDIDError` on duplicate DID; `active_records()` excludes revoked entries; `ValidatorNode.from_key_file()` round-trips correctly
- [x] T028 Run Quickstart Scenarios A–E from `quickstart.md` manually and confirm all exit codes match the contract; document any deviations

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Depends on Phase 1 — blocks all user stories
- **US1 (Phase 3)**: Depends on Phase 2 — MVP; all subsequent stories depend on US1 components
- **US2 (Phase 4)**: Depends on Phase 2 (T010 `generate_bundle` already implemented in US1)
- **US3 (Phase 5)**: Depends on Phase 2 (T011 expiry check already in `verify()` from US1)
- **Polish (Phase 6)**: Depends on Phases 3, 4, 5

### User Story Dependencies

- **US1 (P1)**: Can start after Foundational — implements all core components
- **US2 (P2)**: Can start after Foundational — quorum logic lives in existing `generate_bundle()`/`verify()`; only adds tests
- **US3 (P3)**: Can start after Foundational — expiry check lives in `verify()`; only adds tests + CLI helper

### Within Each Phase

- T005 (`models.py`) MUST complete before T009 (`quorum.py`) and T010 (`bundle.py`)
- T006 (`merkle.py`) MUST complete before T010 (`bundle.py`)
- T007 (`exceptions.py`) MUST complete before T009 and T011
- T008 (CBOR serialisation) MUST complete before T010 and T011
- T010 (`generate_bundle`) MUST complete before T016 (`decpki bundle` CLI)
- T011 (`verify`) MUST complete before T017 (`decpki verify` CLI)

### Parallel Opportunities

```bash
# Phase 2 — all four tasks are independent files:
T005 models.py  |  T006 merkle.py  |  T007 exceptions.py  |  T008 bundle.py (serialisation only)

# Phase 3 — after T005-T008 complete:
T009 quorum.py  |  T012 VerifyResult  |  T013 __init__.py (after models done)
T014 keygen CLI  |  T015 register CLI  (after T009)
T016 bundle CLI  |  T017 verify CLI    (after T010, T011)
T018 inspect CLI (after T008 deserialise)

# Polish — all independent:
T025 tamper test  |  T026 merkle unit tests  |  T027 model unit tests
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1 (Setup)
2. Complete Phase 2 (Foundational — T005–T008)
3. Complete Phase 3 (US1 — T009–T019)
4. **STOP and VALIDATE**: Run quickstart.md Steps 1–4; all five verify outcome paths
5. Ship MVP: offline identity verification works end-to-end

### Incremental Delivery

1. Setup + Foundational → core library ready
2. US1 complete → full CLI + offline verification (MVP)
3. US2 complete → quorum failure hardened + tested
4. US3 complete → expiry enforcement tested
5. Polish → edge cases, tamper detection, quickstart validation

---

## Notes

- `[P]` = different files, no shared in-flight dependencies
- `[Story]` label maps each task to its user story for traceability
- The `three_validators` fixture in `conftest.py` (T004) is the primary test setup; avoid duplicating key generation in individual tests
- Merkle tree MUST handle odd leaf counts by duplicating the last leaf (standard Bitcoin-style)
- CBOR field names are short per data-model.md (`"fmt_ver"`, `"snap_block"`, etc.) — do not use long names in any serialisation code
- `serialise_bundle_for_signing()` MUST set `signatures=[]` before encoding; any other value corrupts signatures
- Key files MUST be written with `os.chmod(path, 0o600)` immediately after creation
