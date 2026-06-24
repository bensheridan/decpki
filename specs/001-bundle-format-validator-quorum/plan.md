# Implementation Plan: Bundle Format & 3-Node Validator Quorum Prototype

**Branch**: `001-bundle-format-validator-quorum` | **Date**: 2026-06-24 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/001-bundle-format-validator-quorum/spec.md`

## Summary

Prototype a CBOR-encoded trust bundle format with SHA-256 Merkle inclusion proofs and
ed25519 validator signatures, paired with a 3-node in-process quorum that can generate
and sign bundles. A client verification function confirms identity validity offline with
zero network calls. Implemented in Python 3.11 using `cbor2` and `cryptography` (PyCA).

## Technical Context

**Language/Version**: Python 3.11+

**Primary Dependencies**: `cbor2` (CBOR encoding), `cryptography` (ed25519, PyCA), `click` (CLI)

**Storage**: JSON file for identity log; binary `.cbor` file for trust bundles

**Testing**: pytest

**Target Platform**: Linux / macOS developer workstation

**Project Type**: library + CLI

**Performance Goals**:
- Merkle proof verification < 100ms for 10,000-identity bundle (single CPU core)
- Bundle generation < 10s for 1,000 identities with 3 validators
- Offline verification round-trip < 2s end-to-end

**Constraints**: Offline-capable verify path (zero network calls); Python 3.11+ required

**Scale/Scope**: Prototype — up to 10,000 identities per bundle

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Gate | Status |
|-----------|------|--------|
| I. Decentralized Trust | No single CA; 2-of-3 validator quorum required for bundle signing | ✅ Pass — quorum enforced in `generate_bundle()` and checked by client |
| II. Offline-First Verification | `verify()` MUST make zero network calls | ✅ Pass — pure local computation; Merkle proof is local math |
| III. Cryptographic Auditability | Identity records on append-only log; Merkle-proofed | ✅ Pass — JSON log is append-only in prototype; Merkle root recomputable |
| IV. Minimal Credential Surface | ed25519 + SHA-256 + W3C DID only | ✅ Pass — no X.509, no RSA; simplified `did:local:` method |
| V. Explicit Revocation Policy | Option B (bundle expiry) selected; grace window configurable | ✅ Pass — `--grace` flag; expiry enforced by client |
| VI. Validator Quorum Governance | N-of-M threshold encoded in bundle; enforced by client | ✅ Pass — `threshold` field in bundle; client rejects if `len(sigs) < threshold` |

**Security Requirements Check**:
- FIPS gap documented in spec Assumptions — ✅ constitution-aligned known gap
- No HSM required for prototype — ✅ explicitly scoped out in Assumptions
- Private keys in mode-0600 files — ✅ enforced by `keygen` command

**Complexity Tracking**: No violations. No Complexity Tracking table needed.

## Project Structure

### Documentation (this feature)

```text
specs/001-bundle-format-validator-quorum/
├── plan.md           # This file
├── research.md       # Phase 0 output
├── data-model.md     # Phase 1 output
├── quickstart.md     # Phase 1 output
├── contracts/
│   ├── cli-contract.md         # CLI command schema
│   └── python-api-contract.md  # Public Python API
└── tasks.md          # Phase 2 output (/speckit-tasks — not yet created)
```

### Source Code (repository root)

```text
src/decpki/
├── __init__.py       # Public API exports: verify(), generate_bundle(), register_identity()
├── models.py         # IdentityRecord, TrustBundle, ValidatorSignature, ValidatorNode, IdentityLog
├── merkle.py         # SHA-256 binary Merkle tree; MerkleProof generation and verification
├── bundle.py         # Bundle generation, canonical CBOR serialisation, signing
├── verify.py         # Client-side verification; VerifyResult, Outcome enum
└── quorum.py         # Signature collection, threshold enforcement, QuorumError

cli/
└── decpki_cli.py     # click CLI: keygen, register, bundle, verify, inspect

tests/
├── unit/             # Pure-function tests: merkle.py, models.py, CBOR round-trips
├── integration/      # End-to-end flows: keygen → register → bundle → verify
└── contract/         # All five verify outcomes; all CLI exit codes

pyproject.toml        # Package config; entry_point: decpki = cli.decpki_cli:cli
```

**Structure Decision**: Single-project layout. Library in `src/decpki/`, CLI in `cli/`.
`src/` layout (PEP 517) prevents accidental imports during development. The CLI is a thin
click wrapper over the library API.
