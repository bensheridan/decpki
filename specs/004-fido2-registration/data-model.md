# Data Model: FIDO2 Registration & Chain Enrolment

## Entities

### EnrolmentRequest

A pending enrolment that has been submitted by the browser but has not yet reached validator quorum. Persisted as a JSON file.

| Field | Type | Description |
|-------|------|-------------|
| `id` | `string (UUID4)` | Unique request identifier |
| `did` | `string` | The DID being registered (e.g. `did:local:<uuid4>`). Assigned at request creation. |
| `public_key_hex` | `string` | The ed25519 public key extracted from the COSE key map, hex-encoded (32 bytes). |
| `public_key_cose` | `bytes (base64)` | The raw COSE key map bytes, preserved for auditability. |
| `credential_id` | `string (base64url)` | The WebAuthn credential ID returned by the authenticator. |
| `request_type` | `enum: "new" \| "add_credential"` | Whether this is a first-time registration or adding a credential to an existing DID. |
| `existing_did` | `string \| null` | Populated for `add_credential` requests; the DID being extended. |
| `submitted_at` | `int (Unix timestamp)` | When the BFF received the submission. |
| `expires_at` | `int (Unix timestamp)` | Request expiry (default: 48 hours after submission). Expired requests cannot be promoted. |
| `status` | `enum: "pending" \| "promoted" \| "expired" \| "cancelled"` | Lifecycle state. |
| `signatures` | `ValidatorSignature[]` | Collected validator co-signatures. |
| `metadata` | `object` | Optional free-form metadata (user agent hint, etc.). |

**Validation rules**:
- `public_key_hex` must be exactly 64 hex characters (32 bytes).
- `did` must match `^did:local:[0-9a-f-]{36}$`.
- `signatures` entries must be from distinct validators in the configured validator set.
- Status transitions: `pending` → `promoted` (quorum reached), `pending` → `expired` (TTL elapsed), `pending` → `cancelled` (manual cancellation).
- A request in `promoted`, `expired`, or `cancelled` state cannot transition to any other state.

---

### ValidatorSignature (embedded in EnrolmentRequest)

| Field | Type | Description |
|-------|------|-------------|
| `validator_name` | `string` | Identifier of the signing validator (matches validator key name, e.g. `"alpha"`). |
| `signature_hex` | `string` | Ed25519 signature over the canonical signing payload, hex-encoded. |
| `signed_at` | `int (Unix timestamp)` | When this signature was added. |

**Signing payload**: `SHA-256(canonical_CBOR({ "id": <request_id>, "did": <did>, "pubkey": <public_key_hex> }))` — the same canonical CBOR encoding used in Feature 003 bundle signing.

---

### Credential (ledger record, extends IdentityRecord)

The existing `IdentityRecord` entity (defined in Feature 003 data-model) stores one `publicKey` per DID. For multi-device support, a DID may have multiple credentials. In this prototype, a second registration creates a new `IdentityRecord` entry with the same `did` and a different `publicKey`.

> **Note**: The bundle format in Feature 003 indexes identities by DID and deduplicates on load. In this feature, the `decpki` CLI `enrol-promote` command may write multiple `IdentityRecord` rows for the same DID — one per credential. The `DecPKIClient.verify()` API looks up by DID and succeeds if any entry matches; no change to the API is required.

---

### Nonce (for re-registration challenge)

Short-lived server-side nonce for ownership proof during `add_credential` flows.

| Field | Type | Description |
|-------|------|-------------|
| `nonce` | `string (base64url, 32 bytes)` | Random challenge. |
| `did` | `string` | The DID whose ownership is being proven. |
| `issued_at` | `int (Unix timestamp)` | When the nonce was issued. |
| `expires_at` | `int (Unix timestamp)` | Nonce expiry (60 seconds after issuance). |

Nonces are stored in-memory in the BFF process (acceptable for prototype; lost on restart). A spent nonce is deleted immediately after verification.

---

## State Transitions

```
EnrolmentRequest lifecycle:

  [Browser submits credential]
          ↓
       PENDING  ←── validator signs (each adds ValidatorSignature)
          ↓                    ↓
    (quorum reached)    (TTL elapsed or cancelled)
          ↓                    ↓
      PROMOTED             EXPIRED / CANCELLED
          ↓
  [IdentityRecord written to ledger]
  [Appears in next trust bundle]
```

---

## Storage Layout (prototype)

```
/tmp/decpki-enrolments/
├── <uuid4>.json           ← one file per EnrolmentRequest
└── promoted/
    └── <uuid4>.json       ← moved here after promotion (audit trail)
```

Nonces are in-memory only (Python dict in BFF process, keyed by `did`).
