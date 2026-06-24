# Data Model: Browser Offline Identity Client

## Entities

---

### TrustBundle (IndexedDB: `bundles` store, key `"current"`)

The decoded and validated bundle object, stored locally after a successful sync.

| Field | Type | Source | Notes |
|-------|------|--------|-------|
| `fmtVer` | `number` | CBOR `fmt_ver` | Must equal `1` |
| `snapBlock` | `number` | CBOR `snap_block` | Block height of snapshot |
| `snapRoot` | `Uint8Array` | CBOR `snap_root` | 32-byte SHA-256 Merkle root |
| `issuedAt` | `number` | CBOR `issued_at` | Unix seconds |
| `expiresAt` | `number` | CBOR `expires_at` | Unix seconds |
| `threshold` | `number` | CBOR `threshold` | Min signatures required |
| `valSet` | `ValidatorEntry[]` | CBOR `val_set` | Ordered list of validators |
| `identities` | `IdentityEntry[]` | CBOR `identities` | Identity records + Merkle proofs |
| `signatures` | `ValidatorSignature[]` | CBOR `signatures` | Validator signatures over bundle |

**Validation rules**:
- `fmtVer === 1` (reject unknown versions)
- `expiresAt > Date.now() / 1000` (reject expired bundles on install)
- `signatures.length >= threshold` (reject under-quorum bundles)
- All `signatures` must verify against `snapRoot` (reject tampered bundles)

---

### ValidatorEntry

| Field | Type | Notes |
|-------|------|-------|
| `name` | `string` | Human-readable validator name |
| `publicKey` | `Uint8Array` | 32-byte ed25519 public key |

---

### IdentityEntry

| Field | Type | Notes |
|-------|------|-------|
| `record` | `IdentityRecord` | The identity data |
| `proof` | `MerkleProof` | Inclusion proof for this record |

---

### IdentityRecord

| Field | Type | Notes |
|-------|------|-------|
| `did` | `string` | W3C DID identifier (`did:local:<slug>`) |
| `publicKey` | `Uint8Array` | 32-byte ed25519 public key |
| `issuedAt` | `number` | Unix seconds |
| `issuedBy` | `string` | Validator name that registered this identity |
| `validUntil` | `number` \| `null` | Unix seconds or null (no per-record expiry) |
| `revokedAt` | `number` \| `null` | Unix seconds or null (not revoked) |
| `metadata` | `Record<string, string>` | Arbitrary key-value metadata |

---

### MerkleProof

| Field | Type | Notes |
|-------|------|-------|
| `leafHash` | `Uint8Array` | 32-byte SHA-256 hash of the leaf |
| `siblings` | `SiblingNode[]` | Ordered sibling hashes from leaf to root |

---

### SiblingNode

| Field | Type | Notes |
|-------|------|-------|
| `h` | `Uint8Array` | 32-byte sibling hash |
| `s` | `"left"` \| `"right"` | Position of the sibling |

---

### ValidatorSignature

| Field | Type | Notes |
|-------|------|-------|
| `name` | `string` | Validator name (matches `valSet` entry) |
| `sig` | `Uint8Array` | 64-byte ed25519 signature |

---

### BundleSyncState (IndexedDB: `meta` store, key `"sync"`)

Tracks the bundle sync lifecycle. Persisted independently of the bundle itself so sync state
survives session restarts.

| Field | Type | Notes |
|-------|------|-------|
| `lastSync` | `number` \| `null` | Unix ms of last successful sync, or null |
| `status` | `SyncStatus` | Current sync status |
| `endpointUrl` | `string` | URL of the bundle endpoint |
| `lastError` | `string` \| `null` | Human-readable error from last failed sync |

---

### SyncStatus (string enum)

| Value | Meaning |
|-------|---------|
| `"idle"` | No sync in progress; last sync succeeded (or never ran) |
| `"syncing"` | Fetch + validate in progress |
| `"failed"` | Last sync failed; old bundle may still be valid |

---

### VerificationResult

The return value of `client.verify(did)`. Not persisted — computed on demand.

| Field | Type | Notes |
|-------|------|-------|
| `outcome` | `Outcome` | See enum below |
| `did` | `string` | The DID that was queried |
| `bundleExpiresAt` | `number` \| `null` | Unix seconds, or null if no bundle loaded |
| `message` | `string` | Human-readable explanation |

---

### Outcome (string enum)

Mirrors the Python `Outcome` enum from `src/decpki/verify.py`.

| Value | Meaning |
|-------|---------|
| `"VALID"` | DID found, all proofs verified, bundle not expired |
| `"NOT_FOUND"` | DID not present in the bundle |
| `"EXPIRED"` | Bundle has passed its `expiresAt` timestamp |
| `"TAMPERED"` | Signature or Merkle proof verification failed |
| `"QUORUM_FAILURE"` | Fewer valid signatures than threshold |
| `"NO_BUNDLE"` | No bundle is stored locally (first launch or cleared storage) |
| `"UNSUPPORTED"` | Browser lacks required cryptographic APIs |

---

## State Transitions

### Bundle Lifecycle

```
[no bundle]
    │ first sync succeeds
    ▼
[current bundle: valid]
    │ 80% of validity elapsed + online         │ storage cleared / private browsing
    ▼                                           ▼
[syncing]                                   [no bundle]
    │ success        │ failure (bundle still valid)
    ▼                ▼
[current bundle: valid]   [current bundle: valid, sync status: failed]
    │ expiresAt passes
    ▼
[current bundle: expired]
    │ sync succeeds          │ offline
    ▼                        ▼
[current bundle: valid]  [current bundle: expired]
```

### Sync Trigger Conditions

Any of these triggers an attempted refresh (no-op if `syncInProgress === true`):

1. SW `activate` event
2. `window` fires `online` → main thread posts `{ type: "SYNC_REQUEST" }` to SW
3. `now > issuedAt + 0.8 * (expiresAt - issuedAt)` (checked on verify or SW activate)

---

## IndexedDB Schema

**Database**: `decpki` (version 1)

| Store | Key Path | Indexes | Description |
|-------|----------|---------|-------------|
| `bundles` | fixed string key `"current"` | — | Decoded TrustBundle object |
| `meta` | fixed string key `"sync"` | — | BundleSyncState object |

Both stores use out-of-line string keys. There is at most one record per store.
