# Feature Specification: Bundle Format & 3-Node Validator Quorum Prototype

**Feature Branch**: `001-bundle-format-validator-quorum`

**Created**: 2026-06-24

**Status**: Draft

**Input**: User description: "prototype the bundle format and a simple 3-node validator quorum"

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Generate and Verify a Trust Bundle (Priority: P1)

A developer running a prototype validator quorum can produce a signed trust bundle
containing active identity records, and a separate client process can verify an identity
from that bundle without any network access.

**Why this priority**: This is the core proof-of-concept. Everything else depends on the
bundle format being correct and the Merkle proofs being verifiable offline.

**Independent Test**: Start 3 validator nodes, register one identity, generate a bundle,
shut down all network interfaces, and verify the identity on a client using only the bundle
file. The test passes when the client confirms the identity as valid.

**Acceptance Scenarios**:

1. **Given** a 3-node validator quorum with 2-of-3 threshold, **When** an identity record is
   submitted, **Then** the identity appears in the next generated trust bundle with a valid
   Merkle inclusion proof.

2. **Given** a signed trust bundle, **When** a client is given the bundle file and a DID to
   verify, **Then** the client confirms the identity as valid using only local computation
   (no outbound network calls).

3. **Given** a trust bundle and a DID that is NOT in the bundle, **When** a client attempts
   verification, **Then** the client returns a clear "identity not found" result without errors.

---

### User Story 2 — Bundle Signing Requires Quorum (Priority: P2)

A bundle that has not received the minimum number of validator signatures (2-of-3) is
rejected by clients.

**Why this priority**: Without this gate, the decentralized trust model is meaningless. A
single compromised validator could issue fraudulent bundles.

**Independent Test**: Produce a bundle signed by only 1 validator, attempt client
verification — client MUST reject it. Produce a bundle signed by 2 validators — client
MUST accept it.

**Acceptance Scenarios**:

1. **Given** a trust bundle signed by only 1 of 3 validators, **When** a client attempts
   to use the bundle, **Then** the client rejects it with a clear quorum-failure message.

2. **Given** a trust bundle signed by 2 of 3 validators, **When** a client uses the bundle,
   **Then** the client accepts it and proceeds with identity verification normally.

---

### User Story 3 — Bundle Expiry Enforces Offline Grace Window (Priority: P3)

A developer can configure the bundle expiry duration. Once a bundle expires, the client
refuses to use it for verification.

**Why this priority**: Bundle expiry is the revocation mechanism (Option B from the design).
Without expiry enforcement, revocation is broken.

**Independent Test**: Generate a bundle with a 5-second expiry, wait 6 seconds, attempt
verification — client MUST refuse and report bundle expiry.

**Acceptance Scenarios**:

1. **Given** a bundle whose expiry timestamp has passed, **When** a client attempts
   verification, **Then** the client refuses and reports the bundle as expired.

2. **Given** a bundle that has not yet expired, **When** a client attempts verification,
   **Then** the client proceeds normally.

---

### Edge Cases

- What happens when a validator node goes offline during bundle generation? (Remaining
  quorum should still be able to issue a bundle if threshold is met.)
- What if the same identity DID is submitted twice? (Second submission should be idempotent
  or produce a clear duplicate error.)
- What if the bundle file is corrupted or tampered with? (Signature verification MUST fail
  and the client MUST report a tamper-evident error.)
- What if the system clock on the client is skewed? (Clock skew beyond a configurable
  tolerance should trigger a warning, not a silent failure.)

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST produce trust bundles in CBOR binary format containing: snapshot
  block reference, Merkle root, a list of active identity records (each with DID, ed25519
  public key, and Merkle inclusion proof), bundle expiry timestamp, and validator signatures.
- **FR-002**: The system MUST support a 3-node validator quorum with a configurable threshold
  (default 2-of-3). Bundles MUST carry the threshold parameter alongside signatures.
- **FR-003**: Identity records MUST be represented as W3C DID Core identifiers paired with
  an ed25519 public key.
- **FR-004**: Merkle proofs MUST use SHA-256 as the hash function. Proof verification MUST
  be executable with no network access.
- **FR-005**: A client library MUST expose a single verification function: given a bundle
  file and a DID, return valid/invalid/not-found/expired/tampered.
- **FR-006**: The validator quorum MUST sign bundles using ed25519 keys. Each validator signs
  the canonical serialised bundle bytes; signatures are collected and embedded in the bundle.
- **FR-007**: Bundle expiry duration MUST be a configurable parameter at bundle-generation
  time (not a compile-time constant).
- **FR-008**: The system MUST include a command-line tool that can: generate a keypair for a
  validator node, register an identity in the quorum, generate a signed trust bundle, and
  verify an identity against a bundle file.
- **FR-009**: The system MUST reject bundles that do not meet the configured quorum threshold
  and return a machine-readable error code.
- **FR-010**: The system MUST detect and report bundle tampering (signature mismatch) as a
  distinct error from quorum failure or expiry.

### Key Entities

- **IdentityRecord**: A DID, an ed25519 public key, issuance block reference, issuing
  validator set, optional expiry block, revocation status, and arbitrary metadata map.
- **TrustBundle**: Snapshot block reference, Merkle root, list of IdentityRecord entries
  each with a Merkle inclusion proof, bundle expiry timestamp, required quorum threshold,
  and a list of validator signatures (validator DID + signature bytes).
- **ValidatorNode**: A validator identity (DID + ed25519 keypair), participation in the
  signing quorum, and the current canonical identity log it holds.
- **MerkleProof**: A list of sibling hashes from a leaf to the root, sufficient to recompute
  the root from any leaf value.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A complete offline verification round-trip (register identity → generate bundle
  → verify on isolated client) completes in under 2 seconds on commodity hardware.
- **SC-002**: Merkle proof verification for a bundle of up to 10,000 identities completes in
  under 100 milliseconds on a single CPU core.
- **SC-003**: Bundle generation with 3 validators and up to 1,000 identity records completes
  in under 10 seconds.
- **SC-004**: All five client verification outcomes (valid, invalid, not-found, expired,
  tampered) are exercised by the test suite with 100% pass rate.
- **SC-005**: A developer unfamiliar with the codebase can complete the quickstart
  (generate validator keys, register an identity, generate a bundle, verify offline) in
  under 15 minutes using only the CLI tool and documentation.

## Assumptions

- This is a prototype: production-grade networking between validators is out of scope. The
  3-node quorum can run as local processes communicating over localhost or via a simple
  in-process simulation.
- Persistence of the identity log is out of scope for the prototype — an in-memory or
  file-backed log is sufficient.
- The prototype does not need to implement the full W3C DID resolution spec; a simplified
  `did:local:<id>` method is acceptable for the prototype phase.
- Revocation via bloom filter (Option A) and stapled revocation (Option C) are out of scope;
  only bundle expiry (Option B) is implemented in this prototype.
- No HSM or hardware key storage is required for the prototype; software keypairs stored in
  files are acceptable.
- The implementation language is not specified here (this is a technology-agnostic spec);
  language choice is deferred to the planning phase.
- Regulatory and FIPS compliance are explicitly out of scope for the prototype, consistent
  with the constitution's known-gap documentation requirement.
