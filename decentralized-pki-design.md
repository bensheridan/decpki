# Decentralized CA Trust — Design Findings

> **Status:** Parked — pending prototype  
> **Goal:** Offline-capable client/server certificate trust without self-signed certificate pain

---

## Problem Statement

Traditional PKI/client cert auth has fundamental structural weaknesses:

- **Centralised trust** — one compromised CA poisons the entire trust chain
- **Revocation is broken** — CRL/OCSP is slow, often ignored, unavailable offline
- **Issuance is bureaucratic** — PKI admin bottlenecks, manual processes
- **No auditability** — no public record of when or why a cert was issued
- **Self-signed pain** — manual trust distribution, no standardised revocation, platform rejection

---

## Core Insight

Blockchain provides a **content-addressed, append-only ledger** that can be **snapshotted and carried offline**.

Instead of trusting a live CA, clients trust a **known-good snapshot of the ledger** — a Merkle root hash baked in at build or sync time.

```
Online:   Chain holds current identity state
Offline:  Client carries signed snapshot + Merkle proof
          "As of block #881423, this identity was valid"
```

This is the same principle as Bitcoin SPV wallets — lightweight clients carry proof enough to verify their specific transactions without the full chain.

---

## Architecture — Three Layers

### Layer 1 — Identity Registry (Chain)

A permissioned consortium chain where **identity records** are published. No X.509. No CA. Just signed records on an agreed ledger.

```
IdentityRecord {
  subject_did:  "did:yourchain:service-payments-3"
  public_key:   ed25519 pubkey bytes
  issued_at:    block #881000
  issued_by:    [validator-A, validator-B]   // N of M signatures
  valid_until:  block #920000                // null = indefinite
  revoked_at:   null
  metadata:     { env: "prod", team: "payments" }
}
```

### Layer 2 — Offline Trust Bundle

At sync time (while online), clients pull a **trust bundle**:

```
TrustBundle {
  snapshot_block:   #881423
  snapshot_root:    sha256:abc123...         // Merkle root of all active identities
  valid_identities: [
    { did, pubkey, merkle_proof }            // proof each record is in the root
  ]
  bundle_signed_by: [validator-A, validator-B, validator-C]
  bundle_expires:   timestamp                // defines offline grace period
}
```

The bundle is signed by N of M validators — same trust model as the chain. Clients receive one bundle update rather than individual certificates. **The bundle is the CA — and it's just a file.**

### Layer 3 — Offline Handshake

```
1. Server presents:   DID + public key + Merkle proof
2. Client checks:
   a. Is this DID in my trust bundle?  (Merkle proof — pure local math, no network)
   b. Does the presented public key match the record?
   c. Is the bundle within its grace window?
   d. Is there a revocation entry in the bundle for this DID?
3. Client issues:     challenge (random nonce)
4. Server responds:   sign(nonce) with private key
5. Client verifies:   signature against pubkey from bundle

→ Mutual trust established. Zero network calls.
```

---

## Revocation Offline

Three strategies with different tradeoff profiles:

| Option | Mechanism | Best For |
|---|---|---|
| **A — Revocation list in bundle** | Bloom filter or list of revoked DIDs in the bundle | Low-revocation environments |
| **B — Short-lived bundles** | Bundle expiry = revocation window. New bundle issued without compromised identity | Pragmatic default |
| **C — Stapled revocation proof** | Connecting party presents a signed "still-valid" assertion timestamped within X hours | When the *other party* can guarantee recent online access |

**Recommended default: Option B.** Maps offline grace period directly to maximum revocation lag. The tradeoff is explicit and configurable (e.g. 24h, 7 days).

---

## Comparison — Old vs New

| Old World | New World |
|---|---|
| Self-signed cert distributed manually | Trust bundle distributed once, covers all identities |
| Trust the CA | Trust the Merkle root (auditable, multi-signed) |
| OCSP/CRL online check | Merkle proof — pure local math |
| Cert expiry = revocation mechanism | Bundle expiry = revocation window |
| X.509 complexity | Simple DID + ed25519 keypair |
| Admin discretion for issuance | Issuance policy encoded in smart contracts |

---

## Practical Stack

| Component | Technology |
|---|---|
| Identity format | W3C DID Core spec |
| Cryptography | ed25519 keys, SHA-256 Merkle trees |
| Chain (initial) | Append-only signed log — e.g. Sigstore Rekor |
| Chain (scaled) | Permissioned consortium chain — e.g. Hyperledger Fabric |
| Bundle format | CBOR or MessagePack (compact binary, embeddable) |
| Validator quorum | 3 validators, 2-of-3 threshold to start |

**Sigstore** is the closest real-world analogue — transparent, append-only, Merkle-proofed, applied to software supply chain. The same pattern applied to service identity.

---

## Open Problems

| Problem | Difficulty | Notes |
|---|---|---|
| Latency in handshake path | High | Needs caching layer for live chain queries |
| Key compromise vs. chain immutability | Medium | Revocation solves it; needs propagation SLA |
| Chain validator governance | High | Organisational/political problem, not technical |
| Regulatory / FIPS compliance | High | Novel — unproven in audited environments |
| Private vs. public chain | Medium | Private chain risks becoming a reimplemented database |

---

## Recommended Next Steps

1. **Prototype the bundle format** — define the CBOR schema, write a simple Merkle proof generator and verifier
2. **Stand up a 3-node validator quorum** — even a simple append-only signed log to start
3. **Read Sigstore Rekor source** — before building, understand how they solved the same core problem for code signing
4. **Define bundle expiry policy** — align offline grace period with acceptable revocation lag for the target environment

---

*Findings from design session — June 2026*
