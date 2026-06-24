# Quickstart: Bundle Format & 3-Node Validator Quorum Prototype

**Goal**: Register an identity, generate a signed trust bundle with a 3-node quorum,
then verify the identity offline. Total time: ~10 minutes.

**Prerequisites**:
- Python 3.11 or later
- `pip install decpki` (or `pip install -e .` from the repo root)

---

## Step 1 — Generate Validator Keypairs (3 nodes)

```bash
decpki keygen --name alpha
decpki keygen --name beta
decpki keygen --name gamma
```

Expected output for each:
```
Validator DID:  did:local:validator-alpha
Public key:     <64 hex chars>
Key file:       alpha.key.json
```

Three key files are created: `alpha.key.json`, `beta.key.json`, `gamma.key.json` (mode 0600).

---

## Step 2 — Register an Identity

Register a service identity using 2 of the 3 validators (meets the 2-of-3 threshold):

```bash
# First generate a keypair for the service identity
python3 -c "
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
import secrets, binascii
key = Ed25519PrivateKey.generate()
pub = key.public_key().public_bytes_raw()
print('Public key:', binascii.hexlify(pub).decode())
"
# Copy the printed hex as PUBKEY in the next command

decpki register \
  --did did:local:payments-svc \
  --pubkey <PUBKEY> \
  --validator alpha.key.json \
  --validator beta.key.json \
  --meta env=prod \
  --meta team=payments
```

Expected output:
```
Registered: did:local:payments-svc
  Block:       1001
  Signed by:   did:local:validator-alpha, did:local:validator-beta
  Log updated: identity_log.json
```

---

## Step 3 — Generate a Signed Trust Bundle

Generate a bundle signed by 2 validators with a 24-hour grace period:

```bash
decpki bundle \
  --validator alpha.key.json \
  --validator beta.key.json \
  --threshold 2 \
  --grace 24h \
  --out bundle.cbor
```

Expected output:
```
Bundle generated:
  Snapshot block:  1001
  Merkle root:     <hex>
  Identities:      1
  Expires:         <tomorrow's date>T<time>Z
  Signed by:       did:local:validator-alpha (✓), did:local:validator-beta (✓)
  Written to:      bundle.cbor  (~1.2 KB)
```

---

## Step 4 — Verify Offline

Simulate an offline client by verifying using only the bundle file:

```bash
decpki verify --bundle bundle.cbor --did did:local:payments-svc
```

Expected output:
```
VALID: did:local:payments-svc is a trusted identity
```

Exit code: 0

---

## Step 5 — Inspect the Bundle

View the full bundle contents in human-readable form:

```bash
decpki inspect --bundle bundle.cbor
```

---

## Validation Scenarios

These scenarios exercise all five verification outcomes.

### Scenario A — Identity not in bundle

```bash
decpki verify --bundle bundle.cbor --did did:local:nonexistent
# Expected: NOT FOUND (exit 4)
```

### Scenario B — Quorum failure (only 1 signature)

```bash
decpki bundle --validator alpha.key.json --threshold 2 --out bundle-bad-quorum.cbor
# Expected: error "fewer validators provided than threshold"

# OR: manually produce a 1-sig bundle (see Python API) and try to verify:
# Expected: QUORUM FAILURE (exit 8)
```

### Scenario C — Expired bundle

```bash
decpki bundle \
  --validator alpha.key.json \
  --validator beta.key.json \
  --grace 2s \
  --out bundle-expiring.cbor

sleep 3

decpki verify --bundle bundle-expiring.cbor --did did:local:payments-svc
# Expected: EXPIRED (exit 5)
```

### Scenario D — Tampered bundle

```bash
# Flip one byte in the bundle file (e.g., offset 100)
python3 -c "
data = open('bundle.cbor', 'rb').read()
data = data[:100] + bytes([data[100] ^ 0xFF]) + data[101:]
open('bundle-tampered.cbor', 'wb').write(data)
"

decpki verify --bundle bundle-tampered.cbor --did did:local:payments-svc
# Expected: TAMPERED (exit 6)
```

### Scenario E — Python API usage

```python
from decpki import verify, Outcome

result = verify("bundle.cbor", "did:local:payments-svc")
assert result.outcome == Outcome.VALID
print(result.message)
```

---

## Project Layout Reference

```text
src/decpki/
├── __init__.py       # Public API: verify(), generate_bundle(), register_identity()
├── models.py         # IdentityRecord, TrustBundle, ValidatorNode, IdentityLog
├── merkle.py         # SHA-256 Merkle tree and proof verification
├── bundle.py         # Bundle generation and canonical serialisation
├── verify.py         # Client-side verification logic
└── quorum.py         # Signature collection and threshold enforcement

cli/
└── decpki_cli.py     # click-based CLI entry point

tests/
├── unit/             # merkle.py, models.py, bundle serialisation
├── integration/      # end-to-end: keygen → register → bundle → verify
└── contract/         # all five verify outcomes, all CLI exit codes
```

See [data-model.md](data-model.md) for entity definitions,
[contracts/cli-contract.md](contracts/cli-contract.md) for the full CLI specification,
and [contracts/python-api-contract.md](contracts/python-api-contract.md) for the library API.
