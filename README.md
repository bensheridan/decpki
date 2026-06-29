# decpki — Decentralized PKI Prototype

[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)

Offline-capable identity verification using a multi-validator trust bundle instead of a Certificate Authority.

Clients verify service identities with **zero network calls** — a signed CBOR file replaces the CA.

## How it works

1. A 3-node validator quorum maintains an append-only identity log
2. Validators co-sign a **trust bundle** — a CBOR snapshot of all active identities with SHA-256 Merkle inclusion proofs
3. Clients verify any identity against the bundle using only local computation (no OCSP, no CRL, no live chain query)
4. Bundle expiry defines the maximum revocation lag (default 24 hours)
5. Users register a FIDO2 passkey → validators co-sign the enrolment → the identity enters the bundle
6. Users log in via WebAuthn assertion → BFF verifies against bundle → issues a JWT session token
7. Session token is used to access protected resources (e.g. `GET /api/me`)
8. Users can view and revoke active sessions per device — revocation is immediate (jti blocklist checked on every request)

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

## FIDO2 Registration (Passkeys)

Users can register a passkey (hardware-backed credential) and enrol it into the trust chain via a BFF + validator co-signing pipeline. Once enrolled, the identity verifies offline like any other.

See [specs/004-fido2-registration/quickstart.md](specs/004-fido2-registration/quickstart.md) for full step-by-step scenarios including:

- New user registration via browser passkey prompt
- Adding a second device to an existing DID
- Algorithm enforcement (ed25519 only — non-ed25519 credentials rejected at the BFF)
- Expired request handling
- Duplicate credential rejection

**Quick version**:

```bash
# 1. Start the BFF
cd bff && pip install -r requirements.txt
uvicorn main:app --port 8000

# 2. Start the browser demo server (separate terminal)
cd browser && BUNDLE_PATH=/tmp/bundle.cbor node demo/server.mjs

# 3. Open http://localhost:3000/register.html — click Register, authenticate with biometric/PIN

# 4. Co-sign via CLI (two validators required)
decpki enrol-sign --request /tmp/decpki-enrolments/<request-id>.json --validator /tmp/alpha.key.json
decpki enrol-sign --request /tmp/decpki-enrolments/<request-id>.json --validator /tmp/beta.key.json
decpki enrol-promote --request /tmp/decpki-enrolments/<request-id>.json --threshold 2

# 5. Regenerate bundle and verify
decpki bundle --validator /tmp/alpha.key.json --validator /tmp/beta.key.json --validator /tmp/gamma.key.json --threshold 2 --grace 24h --out /tmp/bundle.cbor
```

See [browser/README.md](browser/README.md) for the `DecPKIRegistration` JS API.

## FIDO2 Login (BFF Session Issuance)

After registering a passkey, users can log in via a WebAuthn assertion. The BFF verifies the signature against the enrolled public key, checks the DID is active in the current trust bundle, and issues a short-lived JWT session token plus a longer-lived refresh token.

See [specs/005-bff-session-issuance/quickstart.md](specs/005-bff-session-issuance/quickstart.md) for end-to-end scenarios including silent refresh, revoked DID rejection, and logout.

**Quick version** (requires Feature 004 completed — a promoted DID exists):

```bash
# 1. Start the BFF with a session secret
cd bff
SESSION_SECRET=your-secret-at-least-32-chars uvicorn main:app --port 8000

# 2. Start the browser demo server
cd browser && BUNDLE_PATH=/tmp/bundle.cbor node demo/server.mjs

# 3. Open http://localhost:3000/login.html
#    Enter the DID from registration — click Log In — authenticate with biometric/PIN
#    Click "Call Protected Endpoint" → GET /login/verify → HTTP 200 with DID in response

# 4. Click Log Out — subsequent refresh token use returns 401
```

See [browser/README.md](browser/README.md) for the `DecPKISession` JS API.

## Session Management

After logging in, users can view and revoke active sessions from `sessions.html`. Each session corresponds to a login on a specific device. Revoking a session invalidates its JWT immediately (server-side jti blocklist) — no wait for token expiry.

Users can also initiate a second passkey enrolment for their existing DID from the session management page (equivalent to the Feature 004 **Add Credential** flow).

See [specs/007-session-management/quickstart.md](specs/007-session-management/quickstart.md) for end-to-end validation scenarios.

**Quick version** (requires Feature 005 completed — a logged-in session):

```bash
# 1. Start the BFF
SESSION_SECRET=your-secret-at-least-32-chars uvicorn main:app --port 8000

# 2. Start the browser demo server
cd browser && BUNDLE_PATH=/tmp/bundle.cbor node demo/server.mjs

# 3. Log in at http://localhost:3000/login.html
# 4. Open http://localhost:3000/sessions.html
#    — See active sessions; current session is marked "This device"
#    — Click Revoke on another session to invalidate it immediately
#    — Click Add New Device to enrol a second passkey for the same DID
```

## BFF configuration

The BFF is configured entirely via environment variables:

| Variable | Default | Description |
|---|---|---|
| `SESSION_SECRET` | *(required)* | HS256 signing key — minimum 32 characters |
| `SESSION_LIFETIME_SECONDS` | `900` | JWT session token lifetime (15 min) |
| `REFRESH_LIFETIME_SECONDS` | `604800` | Refresh token lifetime (7 days) |
| `BFF_STORE_PATH` | `/tmp/decpki-bff.db` | SQLite database path — see below |
| `BUNDLE_PATH` | `/tmp/bundle.cbor` | Trust bundle CBOR file |
| `ENROLMENT_DIR` | `/tmp/decpki-enrolments` | Enrolment request directory |

### Persistent session store (SQLite)

The BFF stores all session state — refresh tokens, JTI blocklist, and login challenges — in a
SQLite database so sessions survive process restarts.

**Default location**: `/tmp/decpki-bff.db`

```bash
# Use the default path
SESSION_SECRET=... uvicorn main:app --port 8000

# Use a custom path (e.g. inside the project for easier inspection)
BFF_STORE_PATH=./bff-sessions.db SESSION_SECRET=... uvicorn main:app --port 8000

# Disable persistence (in-memory only — state lost on restart)
BFF_STORE_PATH=:memory: SESSION_SECRET=... uvicorn main:app --port 8000
```

The database is created automatically on first start. You can delete it at any time to wipe all
active sessions (all users will need to log in again). The file is a standard SQLite database and
can be inspected with any SQLite client:

```bash
sqlite3 /tmp/decpki-bff.db ".tables"
# challenges  jti_blocklist  refresh_tokens

sqlite3 /tmp/decpki-bff.db "SELECT session_id, did, datetime(issued_at,'unixepoch') FROM refresh_tokens;"
```

## CLI reference

| Command | Description |
|---------|-------------|
| `decpki keygen --name <name>` | Generate a validator keypair |
| `decpki register --did <did> --pubkey <hex> --validator <key.json> ...` | Register an identity (manual) |
| `decpki enrol-sign --request <file> --validator <key.json>` | Co-sign a FIDO2 enrolment request |
| `decpki enrol-promote --request <file> --threshold <n>` | Promote a fully signed enrolment to the ledger |
| `decpki enrol-revoke --did <did> --validator <key.json> ...` | Revoke an identity credential |
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

56 BFF tests plus unit, integration, and contract tests covering Merkle tree, models, CBOR, enrolment, session management, and cross-restart persistence.

## Project layout

```
src/decpki/       # Library: models, merkle, bundle, quorum, verify
cli/              # CLI entry point (click) + enrolment commands
bff/              # FIDO2 BFF (FastAPI) — enrolment + login/session
  session.py      # JWT issue/verify, refresh tokens, login challenges
  bundle_cache.py # Background bundle loader + DID lookup
browser/          # Browser offline client (Service Worker + IndexedDB)
  src/session.js  # DecPKISession — login, refresh, logout
tests/            # unit/, integration/, contract/
specs/            # Design documents, data model, contracts, quickstarts
  001-bundle-format-validator-quorum/
  002-docker-compose-offline-demo/
  003-browser-offline-client/
  004-fido2-registration/
  005-bff-session-issuance/
```

## Status

Prototype — eight features implemented:

| Feature | Description |
|---------|-------------|
| [001](specs/001-bundle-format-validator-quorum/) | Bundle format, validator quorum, Python CLI |
| [002](specs/002-docker-compose-offline-demo/) | Docker Compose offline demo |
| [003](specs/003-browser-offline-client/) | Browser offline client (Service Worker + IndexedDB) |
| [004](specs/004-fido2-registration/) | FIDO2 passkey registration + chain enrolment |
| [005](specs/005-bff-session-issuance/) | FIDO2 login — JWT session tokens, silent refresh, logout |
| [006](specs/006-protected-resource-demo/) | Protected resource demo — `GET /api/me` closes the register → login → access loop |
| [007](specs/007-session-management/) | Session management — list active sessions, per-device revocation, add new passkey |
| [008](specs/008-bff-persistent-storage/) | Persistent BFF storage — SQLite-backed sessions survive process restarts |

Open problems (FIPS compliance, production networking, HSM key storage) are documented in [decentralized-pki-design.md](decentralized-pki-design.md).
