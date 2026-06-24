# Data Model: Bundle Format & 3-Node Validator Quorum Prototype

## Entities

---

### IdentityRecord

Represents a single registered identity in the system.

| Field          | Type              | Description |
|----------------|-------------------|-------------|
| `did`          | string            | W3C DID identifier — `did:local:<slug>` for the prototype |
| `public_key`   | bytes (32)        | ed25519 public key bytes |
| `issued_at`    | int               | Logical block number at issuance |
| `issued_by`    | list[string]      | DIDs of validators that co-signed the issuance |
| `valid_until`  | int \| null       | Logical block number after which the record expires; null = indefinite |
| `revoked_at`   | int \| null       | Logical block number at which revocation was recorded; null = active |
| `metadata`     | map[string, any]  | Arbitrary key-value pairs (e.g., `env`, `team`) |

**Constraints**:
- `did` MUST be unique in the identity log.
- `public_key` MUST be exactly 32 bytes (ed25519 compressed point).
- `issued_by` MUST contain at least `threshold` validator DIDs.
- Once written, all fields except `revoked_at` are immutable.

**Canonical serialisation** (for Merkle leaf hashing):
CBOR-encode the record as a map with keys in lexicographic order, then prepend `0x00`
before SHA-256 hashing to produce the leaf hash.

**State transitions**:
```
REGISTERED ──revoke()──► REVOKED
```

---

### MerkleProof

A cryptographic proof that an IdentityRecord is included in a given Merkle root.

| Field       | Type                            | Description |
|-------------|---------------------------------|-------------|
| `leaf_hash` | bytes (32)                      | SHA-256 of the canonical IdentityRecord CBOR |
| `siblings`  | list[{hash: bytes, side: str}]  | Ordered sibling hashes from leaf to root. `side` is `"left"` or `"right"` — indicates which side the sibling sits on when combining. |
| `root`      | bytes (32)                      | Expected Merkle root (MUST match `TrustBundle.snapshot_root`) |

**Verification algorithm**:
```
current = leaf_hash
for sibling, side in siblings:
    if side == "left":
        current = SHA256(0x01 || sibling || current)
    else:
        current = SHA256(0x01 || current || sibling)
assert current == root
```

---

### ValidatorSignature

One validator's signature over the canonical bundle bytes.

| Field             | Type        | Description |
|-------------------|-------------|-------------|
| `validator_did`   | string      | DID of the signing validator node |
| `validator_pubkey`| bytes (32)  | ed25519 public key of the validator (included for self-contained verification) |
| `signature`       | bytes (64)  | ed25519 signature over the canonical pre-signature bundle bytes |

**What is signed**: The canonical CBOR serialisation of the bundle with the `signatures`
field set to an empty list. All validators sign the identical bytes.

---

### TrustBundle

The complete signed trust artifact delivered to clients.

| Field              | Type                        | Description |
|--------------------|----------------------------|-------------|
| `format_version`   | int                         | Bundle schema version; `1` for this prototype |
| `snapshot_block`   | int                         | Logical block number of this snapshot |
| `snapshot_root`    | bytes (32)                  | SHA-256 Merkle root of all active IdentityRecords |
| `issued_at`        | int                         | Unix timestamp (seconds) when the bundle was generated |
| `expires_at`       | int                         | Unix timestamp (seconds) when the bundle expires |
| `threshold`        | int                         | Minimum validator signatures required (e.g., 2) |
| `validator_set`    | list[string]                | DIDs of all known validators at time of issuance |
| `identities`       | list[IdentityEntry]         | Active identities with inclusion proofs (see below) |
| `signatures`       | list[ValidatorSignature]    | Collected validator signatures; MUST have `>= threshold` entries |

**IdentityEntry** (embedded in `identities`):

| Field         | Type           | Description |
|---------------|----------------|-------------|
| `record`      | IdentityRecord | The full identity record |
| `proof`       | MerkleProof    | Inclusion proof for this record in `snapshot_root` |

**Constraints**:
- `len(signatures) >= threshold` — enforced by client before any verification.
- `expires_at > issued_at` — enforced at generation time.
- `snapshot_root` MUST be recomputable from `identities[*].record` by the client.
- `format_version` MUST be `1` for this prototype; unknown versions MUST be rejected.

**Canonical serialisation** (for signing): CBOR-encode the full bundle with `signatures = []`,
keys in lexicographic order (`canonical=True` in cbor2).

---

### ValidatorNode

A participant in the signing quorum.

| Field          | Type      | Description |
|----------------|-----------|-------------|
| `did`          | string    | This validator's DID — `did:local:validator-<name>` |
| `public_key`   | bytes (32)| ed25519 public key |
| `private_key`  | bytes (32)| ed25519 private key seed (stored in local key file; never leaves the node) |
| `log_path`     | string    | Path to the JSON identity log file this node maintains |

**Persistence**: Private key stored as a JSON file: `{"did": "...", "private_key_seed": "<hex>"}`.
The file MUST be kept secret (mode `0600`). Public key is derived from the seed at load time.

---

## Entity Relationships

```
ValidatorNode  ──signs──►  TrustBundle
ValidatorNode  ──maintains──►  IdentityLog (list of IdentityRecord)
TrustBundle  ──embeds──►  IdentityEntry  ──contains──►  IdentityRecord + MerkleProof
MerkleProof  ──proves inclusion in──►  TrustBundle.snapshot_root
```

---

## CBOR Wire Format

The CBOR bundle is a top-level map. All maps use canonical (sorted-key) CBOR encoding.
Field names are short ASCII strings as map keys.

```
{
  "fmt_ver":    1,                           # uint
  "snap_block": 1001,                        # uint
  "snap_root":  h'<32 bytes>',               # bstr
  "issued_at":  1750000000,                  # uint (unix seconds)
  "expires_at": 1750086400,                  # uint (unix seconds)
  "threshold":  2,                           # uint
  "val_set":    ["did:local:v-alpha", ...],  # array of tstr
  "identities": [                            # array of maps
    {
      "did":       "did:local:payments-svc",
      "pubkey":    h'<32 bytes>',
      "issued_at": 1000,
      "issued_by": ["did:local:v-alpha", "did:local:v-beta"],
      "valid_until": null,
      "revoked_at":  null,
      "meta":      {"env": "prod"},
      "proof": {
        "leaf":      h'<32 bytes>',
        "siblings":  [{"h": h'<32>', "s": "right"}, ...],
        "root":      h'<32 bytes>'
      }
    }
  ],
  "signatures": [                            # array of maps; empty when signing
    {
      "val_did":  "did:local:v-alpha",
      "val_pk":   h'<32 bytes>',
      "sig":      h'<64 bytes>'
    }
  ]
}
```

**Field name shortening rationale**: CBOR does not compress key strings; short keys reduce
bundle size meaningfully at scale (e.g., 10k identities × 8 fields × ~5 chars saved = ~400 KB).
