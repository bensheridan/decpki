<!--
  SYNC IMPACT REPORT
  ==================
  Version change:       (unversioned template) → 1.0.0
  Modified principles:  N/A — initial ratification
  Added sections:       Core Principles (I–VI), Security Requirements, Development Workflow, Governance
  Removed sections:     N/A
  Templates requiring updates:
    ✅ .specify/templates/plan-template.md  — Constitution Check section already generic; no update needed
    ✅ .specify/templates/spec-template.md  — no principle-driven mandatory sections to add
    ✅ .specify/templates/tasks-template.md — task structure compatible with principles
  Deferred TODOs:       None
-->

# Decentralized PKI Constitution

## Core Principles

### I. Decentralized Trust (NON-NEGOTIABLE)

No single Certificate Authority. Trust MUST be anchored in a multi-validator-signed Merkle root
published to an append-only ledger. Any design that introduces a single point of trust compromise
violates this principle and MUST be rejected.

- Identity records MUST require N-of-M validator signatures (minimum 2-of-3) to be accepted.
- Clients MUST NOT trust any identity that cannot be verified against a signed trust bundle.
- Self-signed certificates and manually distributed trust anchors are PROHIBITED.

### II. Offline-First Verification (NON-NEGOTIABLE)

The verification path MUST complete with zero network calls. Every design decision in the
handshake layer MUST be evaluated against the question: "does this work with no connectivity?"

- Clients MUST carry a trust bundle (Merkle root + inclusion proofs) sufficient for full verification.
- Merkle proof verification MUST be pure local computation — no OCSP, no CRL, no live chain query.
- The trust bundle MUST include a revocation list or bloom filter covering the offline grace window.
- Bundle expiry defines the maximum revocation lag; this window MUST be explicitly configured and
  documented per deployment environment.

### III. Cryptographic Auditability

All identity issuance and revocation events MUST be recorded on an append-only ledger. The ledger
MUST be Merkle-structured so any record's inclusion can be proven to any observer holding only
the root hash.

- Identity records MUST be immutable once written; revocation is a new record, not a mutation.
- Bundle roots MUST be derivable from the public ledger state — no off-chain trust state.
- Ledger choice MUST support public auditability (e.g., Sigstore Rekor or equivalent transparent log).

### IV. Minimal Credential Surface

The system MUST use the simplest cryptographic primitives that satisfy the security requirements.
Complexity is a liability.

- Identity format MUST be W3C DID Core spec (`did:yourchain:<id>`).
- Cryptography MUST use ed25519 keys and SHA-256 Merkle trees. RSA and X.509 are PROHIBITED.
- Bundle wire format MUST be CBOR or MessagePack — compact binary, no XML, no PEM.
- No credential type beyond DID + ed25519 keypair MAY be introduced without a constitution amendment.

### V. Explicit Revocation Policy

Revocation strategy MUST be selected per deployment and its tradeoffs MUST be documented.
Implicit or undefined revocation behaviour is PROHIBITED.

- The default revocation strategy is Option B (short-lived bundles): bundle expiry equals the
  maximum acceptable revocation lag.
- Alternative strategies (bloom filter in bundle, stapled revocation proof) MAY be used when the
  deployment context is documented and the tradeoffs are explicitly accepted.
- Revocation propagation SLA MUST be defined before any production deployment.

### VI. Validator Quorum Governance

All chain writes and trust bundle issuance MUST require a documented quorum of validators.
Unilateral trust decisions by any single party are PROHIBITED.

- Minimum starting quorum: 3 validators, 2-of-3 threshold.
- Quorum parameters MUST be encoded in smart contract or chain configuration — not in application
  code or documentation alone.
- Validator set changes MUST themselves require quorum approval and MUST be recorded on-chain.

## Security Requirements

- Key compromise response MUST be covered by the chosen revocation strategy before deployment.
- Private keys for validators MUST be held in HSMs or equivalent hardware-backed stores.
- Bundle signing keys MUST be rotated on a documented schedule.
- FIPS compliance status MUST be explicitly assessed for any regulated deployment; ed25519 is not
  FIPS 140-2 approved — this MUST be documented as a known gap until resolved.
- All open problems listed in the design doc (latency, key compromise, regulatory compliance) MUST
  have an assigned owner and mitigation plan before the system is promoted to production.

## Development Workflow

- Prototype first: bundle format (CBOR schema + Merkle proof generator/verifier) MUST be validated
  before chain infrastructure work begins.
- Sigstore Rekor source MUST be reviewed before implementing any transparent log component — do not
  reinvent solved problems.
- All components MUST have an independently runnable integration test that covers the offline
  handshake path end-to-end.
- Bundle expiry policy MUST be encoded as a configuration parameter, not a constant.
- Architecture decisions that deviate from the design doc MUST be recorded as ADRs in `docs/adr/`.

## Governance

This constitution supersedes all other practices and informal agreements for this project.
Amendments require:

1. A written proposal describing the change and its rationale.
2. Approval from the project lead and at least one other contributor.
3. A migration plan for any in-flight features affected by the change.
4. A version bump following semantic versioning:
   - **MAJOR**: removal or redefinition of a non-negotiable principle.
   - **MINOR**: new principle or section added; material guidance expansion.
   - **PATCH**: clarifications, wording, typo fixes.

All feature plans MUST include a Constitution Check gate (see `.specify/templates/plan-template.md`).
Complexity violations MUST be justified in the plan's Complexity Tracking table before work begins.

**Version**: 1.0.0 | **Ratified**: 2026-06-24 | **Last Amended**: 2026-06-24
