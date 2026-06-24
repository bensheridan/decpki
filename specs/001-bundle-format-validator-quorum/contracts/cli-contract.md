# CLI Contract: `decpki` Command-Line Tool

The `decpki` CLI is the primary interface for the prototype. All sub-commands follow the
pattern `decpki <command> [options]`.

---

## Global Options

| Flag           | Default | Description |
|----------------|---------|-------------|
| `--log PATH`   | `identity_log.json` | Path to the shared identity log file |
| `--verbose`    | off     | Print detailed operation output |

---

## Commands

### `decpki keygen`

Generate a new validator keypair and write it to a key file.

```
decpki keygen --name <name> [--out <path>]
```

| Argument      | Required | Description |
|---------------|----------|-------------|
| `--name NAME` | yes      | Short name for the validator (e.g., `alpha`). DID will be `did:local:validator-<name>`. |
| `--out PATH`  | no       | Output file path. Default: `<name>.key.json` |

**Output** (stdout):
```
Validator DID:  did:local:validator-alpha
Public key:     <hex>
Key file:       alpha.key.json
```

**Key file format** (JSON, mode 0600):
```json
{
  "did": "did:local:validator-alpha",
  "public_key": "<hex>",
  "private_key_seed": "<hex>"
}
```

**Exit codes**: 0 = success, 1 = key file already exists (use `--force` to overwrite)

---

### `decpki register`

Register an identity in the log. Requires signatures from at least `threshold` validators.

```
decpki register --did <did> --pubkey <hex> --validator <key1.json> [--validator <key2.json>] ...
                [--meta key=value ...] [--valid-until-block N]
```

| Argument              | Required | Description |
|-----------------------|----------|-------------|
| `--did DID`           | yes      | DID of the identity to register (e.g., `did:local:payments-svc`) |
| `--pubkey HEX`        | yes      | ed25519 public key of the identity (64 hex chars = 32 bytes) |
| `--validator PATH`    | yes (≥2) | Key file for a signing validator. Repeat flag for each validator. |
| `--meta KEY=VALUE`    | no       | Metadata field. Repeatable. |
| `--valid-until-block N`| no     | Block number after which the record expires. Omit for indefinite. |

**Output** (stdout):
```
Registered: did:local:payments-svc
  Block:       1001
  Signed by:   did:local:validator-alpha, did:local:validator-beta
  Log updated: identity_log.json
```

**Exit codes**: 0 = success, 2 = DID already registered, 3 = insufficient validators provided

---

### `decpki bundle`

Generate a signed trust bundle from the current identity log.

```
decpki bundle --validator <key1.json> [--validator <key2.json>] ...
              [--threshold N] [--grace <duration>] [--out <path>]
```

| Argument           | Required | Description |
|--------------------|----------|-------------|
| `--validator PATH` | yes (≥2) | Key file for a signing validator. Repeat for each. |
| `--threshold N`    | no       | Minimum signatures required. Default: 2. |
| `--grace DURATION` | no       | Bundle validity window. Format: `24h`, `7d`, `3600s`. Default: `24h`. |
| `--out PATH`       | no       | Output bundle file path. Default: `bundle.cbor` |

**Output** (stdout):
```
Bundle generated:
  Snapshot block:  1001
  Merkle root:     <hex>
  Identities:      3
  Expires:         2026-06-25T12:00:00Z
  Signed by:       did:local:validator-alpha (✓), did:local:validator-beta (✓)
  Written to:      bundle.cbor  (4.2 KB)
```

**Exit codes**: 0 = success, 3 = fewer validators provided than threshold

---

### `decpki verify`

Verify an identity against a trust bundle. Zero network calls.

```
decpki verify --bundle <path> --did <did>
```

| Argument        | Required | Description |
|-----------------|----------|-------------|
| `--bundle PATH` | yes      | Path to the `.cbor` bundle file |
| `--did DID`     | yes      | DID to verify |

**Output** (stdout, one of):

| Result    | Exit code | Message |
|-----------|-----------|---------|
| valid     | 0         | `VALID: did:local:payments-svc is a trusted identity` |
| not-found | 4         | `NOT FOUND: did:local:payments-svc is not in this bundle` |
| expired   | 5         | `EXPIRED: bundle expired at 2026-06-24T12:00:00Z (24m ago)` |
| tampered  | 6         | `TAMPERED: signature verification failed for did:local:validator-alpha` |
| invalid   | 7         | `INVALID: Merkle proof verification failed for did:local:payments-svc` |
| quorum    | 8         | `QUORUM FAILURE: bundle has 1 signature(s), threshold is 2` |

**Verification steps** (always in this order, short-circuit on first failure):
1. Check `format_version == 1`
2. Check `len(signatures) >= threshold`
3. Verify each signature in `signatures` against `validator_pubkey` and canonical bundle bytes
4. Check `expires_at > time.time()`
5. Recompute Merkle root from `identities[*].record`; assert it equals `snapshot_root`
6. Look up `did` in `identities`; if not found → NOT FOUND
7. Verify `proof.root == snapshot_root` and walk the sibling list

---

### `decpki inspect`

Print a human-readable summary of a bundle file.

```
decpki inspect --bundle <path>
```

**Output** (stdout):
```
Bundle: bundle.cbor
  Format version: 1
  Snapshot block: 1001
  Merkle root:    <hex>
  Issued:         2026-06-24T12:00:00Z
  Expires:        2026-06-25T12:00:00Z  (23h 51m remaining)
  Threshold:      2
  Validator set:  did:local:validator-alpha, did:local:validator-beta, did:local:validator-gamma
  Signatures:     2 (✓ quorum met)
  Identities:     3

  Identity 1: did:local:payments-svc
    Public key:   <hex>
    Issued block: 1000
    Issued by:    did:local:validator-alpha, did:local:validator-beta
    Expires:      (indefinite)
    Revoked:      no
    Metadata:     env=prod, team=payments
```

**Exit codes**: 0 = success, 9 = file not found or not valid CBOR
