# decpki — Decentralized PKI Prototype

Offline-capable identity verification using a multi-validator trust bundle instead of a Certificate Authority.

Clients verify service identities with **zero network calls** — a signed CBOR file replaces the CA.

## How it works

1. A 3-node validator quorum maintains an append-only identity log
2. Validators co-sign a **trust bundle** — a CBOR snapshot of all active identities with SHA-256 Merkle inclusion proofs
3. Clients verify any identity against the bundle using only local computation (no OCSP, no CRL, no live chain query)
4. Bundle expiry defines the maximum revocation lag (default 24 hours)

See [decentralized-pki-design.md](decentralized-pki-design.md) for the full design rationale.

## Quickstart

**Requirements**: Python 3.11+

```bash
pip install -e .
```

### 1. Generate validator keypairs

```bash
decpki keygen --name alpha
decpki keygen --name beta
decpki keygen --name gamma
```

### 2. Register an identity

```bash
# Generate a keypair for the service
PUBKEY=$(python3 -c "
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
import binascii
k = Ed25519PrivateKey.generate()
print(binascii.hexlify(k.public_key().public_bytes_raw()).decode())
")

decpki register \
  --did did:local:payments-svc \
  --pubkey $PUBKEY \
  --validator alpha.key.json \
  --validator beta.key.json \
  --meta env=prod
```

### 3. Generate a signed trust bundle

```bash
decpki bundle \
  --validator alpha.key.json \
  --validator beta.key.json \
  --grace 24h \
  --out bundle.cbor
```

### 4. Verify offline

```bash
decpki verify --bundle bundle.cbor --did did:local:payments-svc
# VALID: did:local:payments-svc is a trusted identity
```

No network required. The bundle file is the only input.

## CLI reference

| Command | Description |
|---------|-------------|
| `decpki keygen --name <name>` | Generate a validator keypair |
| `decpki register --did <did> --pubkey <hex> --validator <key.json> ...` | Register an identity |
| `decpki bundle --validator <key.json> ... --grace <24h\|7d\|3600s>` | Generate a signed bundle |
| `decpki verify --bundle <file> --did <did>` | Verify a DID (offline) |
| `decpki inspect --bundle <file>` | Print bundle contents |

### Verify exit codes

| Code | Meaning |
|------|---------|
| 0 | Valid |
| 4 | DID not found in bundle |
| 5 | Bundle expired |
| 6 | Signature tampered |
| 7 | Merkle proof invalid |
| 8 | Quorum not met (too few signatures) |

## Python API

```python
from decpki import verify, generate_bundle, register_identity, Outcome

result = verify("bundle.cbor", "did:local:payments-svc")
if result.outcome == Outcome.VALID:
    print("trusted:", result.record.did)
```

See [specs/001-bundle-format-validator-quorum/contracts/python-api-contract.md](specs/001-bundle-format-validator-quorum/contracts/python-api-contract.md) for the full API.

## Trust model

- Bundle requires **2-of-3 validator signatures** to be accepted by clients
- Identities use **W3C DID** format (`did:local:<id>`) + **ed25519** keypairs
- Merkle proofs use **SHA-256**; verification is pure arithmetic — no external calls
- Revocation is handled by issuing a new bundle that omits revoked identities (Option B)

## Demo

See the offline guarantee in action with two Docker containers — one that generates a trust bundle, and one that verifies an identity with the network physically cut.

**Prerequisites**: Docker Engine with Compose V2

```bash
# Standard demo (24-hour bundle) — exits 0
./demo.sh

# Expiry demo (30-second bundle, shows EXPIRED after grace lapses) — exits 5
./demo.sh --short-expiry

# Skip image rebuild on subsequent runs
./demo.sh --no-build
```

The server container generates a 3-node quorum, registers `did:local:demo-server`, signs a bundle, and exits. The orchestrator cuts the network. The client verifies with zero network calls.

See [specs/002-docker-compose-offline-demo/quickstart.md](specs/002-docker-compose-offline-demo/quickstart.md) for full validation scenarios.

## Running tests

```bash
pip install pytest
pytest
```

24 tests covering unit (Merkle tree, models, CBOR), integration (end-to-end offline flow), and contract (all 5 verify outcomes, quorum threshold, expiry, tamper detection).

## Project layout

```
src/decpki/       # Library: models, merkle, bundle, quorum, verify
cli/              # CLI entry point (click)
tests/            # unit/, integration/, contract/
specs/            # Design documents, data model, contracts, quickstart
```

## Status

Prototype — see [specs/001-bundle-format-validator-quorum/](specs/001-bundle-format-validator-quorum/) for the full design and implementation plan. Open problems (FIPS compliance, production networking, HSM key storage) are documented in the design doc.
