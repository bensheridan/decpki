# Research: Bundle Format & 3-Node Validator Quorum Prototype

## Decision 1: Implementation Language

**Decision**: Python 3.11+

**Rationale**: All required primitives exist in mature Python libraries. No compilation step
lowers the barrier for the quickstart success criterion (< 15 min for unfamiliar developer).
Python's cbor2 library supports deterministic (canonical) serialisation, which is required
for reproducible signing. The `cryptography` (PyCA) library provides production-grade ed25519.

**Alternatives considered**:
- Go: Natural choice given Sigstore/Rekor are Go. Better binary distribution. Preferred for
  production but slower prototyping velocity.
- Rust: Best-in-class crypto safety guarantees; `rcgen`, `ring`. Significant overhead for a
  prototype that must be stood up quickly.

**Upgrade path**: The CBOR schema and Merkle proof algorithm are language-agnostic. A Go or
Rust re-implementation can consume the same bundle binary format.

---

## Decision 2: CBOR Library

**Decision**: `cbor2` (Python)

**Rationale**: Mature, pure-Python, widely used in IETF protocol implementations. Supports
deterministic encoding via `canonical=True` — essential so all validators produce identical
bytes before signing.

**Alternatives considered**:
- `cbor` (older package): Less maintained, fewer features.
- MessagePack (`msgpack`): Also specified in the design doc as acceptable; cbor2 chosen
  because CBOR is the IETF standard (RFC 8949) and has richer type support.

---

## Decision 3: Cryptography Library

**Decision**: `cryptography` (PyCA) — `Ed25519PrivateKey` / `Ed25519PublicKey`

**Rationale**: The de-facto standard for Python cryptography. ed25519 support is mature and
tested. SHA-256 available via `hashlib` (stdlib) — no dependency needed for the Merkle hash.

**Alternatives considered**:
- `PyNaCl`: Wraps libsodium; good but `cryptography` is more widely deployed in the Python
  ecosystem.
- `pynacl` via `libnacl`: Lower-level; unnecessary complexity for a prototype.

---

## Decision 4: Merkle Tree Implementation

**Decision**: Custom implementation, ~50 LOC, binary SHA-256 tree

**Rationale**: A standard binary Merkle tree with SHA-256 leaf and node hashing is simple
enough that adding a dependency would increase complexity more than it removes. The algorithm
is well-specified:
- Leaf hash: `SHA256(0x00 || value_bytes)`
- Node hash: `SHA256(0x01 || left || right)`
- Inclusion proof: ordered list of sibling hashes from leaf to root, with a direction bit

**Alternatives considered**:
- `pymerkle`: Exists but adds a dependency for < 50 lines of straightforward code.
- Sparse Merkle tree: More powerful but unnecessary for a fixed-snapshot bundle.

**Proof format**: List of `{"sibling": hex, "position": "left"|"right"}` dicts embedded in
the CBOR bundle.

---

## Decision 5: Validator Quorum Simulation

**Decision**: In-process simulation — three `ValidatorNode` Python objects in the same process

**Rationale**: The spec explicitly scopes the prototype to localhost/in-process validators.
This eliminates all networking complexity while still exercising the quorum threshold logic,
signature collection, and bundle generation path.

**Interaction model**: `BundleGenerator` calls `sign(bundle_bytes)` on each `ValidatorNode`.
It collects signatures until the threshold is reached (or all nodes are asked). The resulting
signature list is embedded in the bundle.

**Alternatives considered**:
- Three separate OS processes via subprocess: More realistic but adds IPC complexity with no
  prototype value.
- HTTP microservices: Production pattern; out of scope for prototype.

---

## Decision 6: Identity Log Storage

**Decision**: JSON file per validator node, loaded into memory on startup

**Rationale**: Inspectable, no database dependency, sufficient for a prototype with < 1,000
identities (per the success criteria). Each validator holds its own view of the log; in the
prototype they share a single file for simplicity.

**Alternatives considered**:
- SQLite: More robust but unnecessary for a prototype.
- Pure in-memory (no persistence): Would require re-registering identities every run, making
  quickstart harder to follow.

---

## Decision 7: DID Method

**Decision**: `did:local:<slug>` — a simplified DID method for the prototype

**Rationale**: Full W3C DID resolution requires a resolver, which is out of scope. The DID
is used purely as an opaque identifier string in the bundle; clients compare it as a string.
The `slug` is any URL-safe alphanumeric string chosen at registration time.

**Migration path**: Switching to `did:web:`, `did:key:`, or a custom method at production
is a schema change to the identity records only; the bundle format and Merkle logic are unaffected.

---

## Decision 8: Bundle Expiry Format

**Decision**: Unix timestamp (integer, seconds since epoch) stored as a CBOR `uint`

**Rationale**: Universally parseable without timezone ambiguity. Integer comparison is trivial.
The bundle generation CLI accepts a `--grace-period` flag in seconds/minutes/hours (human-
friendly input) which is converted to an absolute expiry timestamp at generation time.

---

## Summary: Resolved Technical Context

| Field                | Value                                      |
|----------------------|--------------------------------------------|
| Language/Version     | Python 3.11+                               |
| Primary Dependencies | cbor2, cryptography, click                 |
| Storage              | JSON file (identity log), binary file (bundle) |
| Testing              | pytest                                     |
| Target Platform      | Linux/macOS developer workstation          |
| Project Type         | library + CLI                              |
| Performance Goals    | Verification < 100ms for 10k identities; bundle gen < 10s for 1k identities |
| Constraints          | Offline-capable; no network calls in verify path |
| Scale/Scope          | Prototype; up to 10k identities per bundle |
