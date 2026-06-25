# Research: FIDO2 Registration & Chain Enrolment

## Decision 1: WebAuthn Library (Browser)

**Decision**: Use `@simplewebauthn/browser` for the browser-side credential creation call.

**Rationale**: `navigator.credentials.create()` and the WebAuthn API have well-known cross-browser quirks — particularly around how authenticator data is encoded, how exclusion lists are handled, and how cancellation errors surface. `@simplewebauthn/browser` normalises these differences and provides TypeScript types. It is widely used, actively maintained, and adds < 10 KB to the bundle. The server-side complement (`@simplewebauthn/server`) is not used here because the BFF is Python; CBOR decoding and signature verification happen in Python via `cbor2` and `cryptography`.

**Alternatives considered**:
- **Raw `navigator.credentials.create()`**: Works, but requires hand-rolling cross-browser compatibility shims and CBOR parsing of the attestation object. Acceptable for a prototype but adds risk.
- **`webauthn-json`**: Lighter wrapper (JSON-serialises the credential). Rejected because it doesn't provide the typed helpers for extracting the COSE public key from the attestation object.

---

## Decision 2: COSE Algorithm Restriction (ed25519 only)

**Decision**: The BFF MUST reject any credential whose COSE algorithm identifier is not `-8` (EdDSA / ed25519). All other algorithms (P-256 / ES256 = -7, RS256 = -257, etc.) return HTTP 422 with a clear error message.

**Rationale**: Constitution Principle IV prohibits non-ed25519 keys. WebAuthn authenticators negotiate the algorithm from a list supplied by the relying party during the `create()` call. By setting `pubKeyCredParams` to `[{ type: "public-key", alg: -8 }]`, the browser will only create an ed25519 credential. However, the BFF must also enforce this independently since the client is not trusted. The `cryptography` Python library supports ed25519 public key import from raw bytes; `cbor2` decodes the COSE key map.

**Alternatives considered**:
- **Support P-256 as a fallback**: Many older security keys (YubiKey 4 and below) do not support ed25519. Rejected — constitution is non-negotiable. Prototype targets modern devices; a future constitution amendment would be needed to add P-256.
- **Accept any algorithm and convert**: Not cryptographically feasible; key algorithms are not interchangeable.

---

## Decision 3: BFF Framework (Python)

**Decision**: FastAPI with Uvicorn, matching the Python 3.11 ecosystem already used by `decpki`.

**Rationale**: FastAPI provides automatic request validation via Pydantic, OpenAPI schema generation for free, and is trivially testable with `httpx` + `pytest`. The BFF is a thin layer (receive credential → validate COSE → write enrolment request file → return pending ID), so framework complexity is irrelevant. FastAPI is the natural choice for a modern Python HTTP service.

**Alternatives considered**:
- **Flask**: Would work. Rejected for lack of built-in request validation; Pydantic integration requires boilerplate.
- **Node.js / Express**: Would align with the browser JS codebase, but the BFF also invokes Python-based validator logic. Keeping everything in Python avoids a polyglot server.

---

## Decision 4: Enrolment Request Storage (Prototype)

**Decision**: Enrolment requests are stored as JSON files under a configurable directory (default: `/tmp/decpki-enrolments/`). Each file is named `<request-id>.json` and contains the full request plus any collected validator signatures.

**Rationale**: The existing `decpki` CLI is entirely file-based (keypairs as `.key.json`, bundles as `.cbor`). Using the same pattern for enrolment requests keeps the prototype coherent and avoids introducing a database dependency. The request ID is a UUID4.

**Alternatives considered**:
- **SQLite**: Would provide atomicity and querying. Rejected — overkill for a demo; adds a schema migration concern.
- **In-memory**: Lost on restart. Rejected — the multi-step co-signing flow requires persistence across CLI invocations.

---

## Decision 5: Validator Co-Signing Flow

**Decision**: Two new `decpki` CLI sub-commands: `decpki enrol` (called by the BFF, or manually, to create a pending request file) and `decpki enrol-sign` (called by each validator to add their signature to a pending request). When the request file contains ≥ threshold signatures, `decpki enrol-promote` writes the identity to the ledger and marks the request as complete.

**Rationale**: Mirrors the existing CLI pattern where operators run `decpki bundle --validator ...` manually. FIDO2 enrolment is not expected to be high-frequency in the prototype; manual CLI signing is acceptable.

**Alternatives considered**:
- **Automatic co-signing on BFF submit**: Would require validators to be API-accessible, adding network infrastructure. Rejected for prototype scope.
- **Single combined command**: The three-step (create → sign × N → promote) model makes it possible for each validator to sign independently from their own machine, which is realistic for a distributed validator set.

---

## Decision 6: DID Assignment

**Decision**: For a new user, the BFF generates a `did:local:<uuid4>` DID at enrolment request time. This DID is returned to the browser immediately and is stable — even before the identity is promoted, the DID is reserved. For re-registration (adding a credential to an existing DID), the existing DID is supplied by the client and verified via a signed challenge.

**Rationale**: Deterministic DID assignment avoids collisions and gives the user a stable identifier from the first interaction. UUID4 avoids any PII in the DID. The existing `decpki register --did` flow accepts a DID string, so no format changes are needed.

**Alternatives considered**:
- **DID = hash of public key**: Would break for multi-device (different public keys → different DIDs for the same user). Rejected.
- **DID = user-supplied string**: Risk of collisions and namespace squatting. Rejected for prototype; could be a future extension for human-readable DIDs.

---

## Decision 7: Multi-Device Ownership Proof

**Decision**: To add a second credential to an existing DID, the browser must present a WebAuthn assertion (signature) using an existing, valid credential for that DID, signing a server-issued nonce. The BFF verifies this assertion before creating an additive enrolment request.

**Rationale**: This is the standard WebAuthn re-authentication pattern. It proves control of an existing credential without any out-of-band channel. A server nonce (random, short-lived) prevents replay. The BFF verifies the assertion using the stored public key for the DID.

**Alternatives considered**:
- **Admin approval**: Simpler but requires human involvement. Rejected as primary mechanism.
- **Recovery code**: Out-of-band; adds credential management complexity. Noted as a future extension.

---

## Decision 8: Attestation Format

**Decision**: Accept `none` attestation format only. The BFF does not validate hardware attestation certificates. The `attestationObject` is parsed only to extract the COSE public key from the `authData` field.

**Rationale**: Hardware attestation requires access to FIDO Alliance metadata (MDS3) and is complex to validate correctly. For a decentralised PKI prototype, the trust model is the validator quorum — not the authenticator manufacturer. Accepting `none` means the browser may be asked to strip attestation, or the server simply ignores it. This is the standard privacy-preserving mode recommended by the W3C spec.

**Alternatives considered**:
- **Full attestation validation**: Would allow the system to require specific authenticator models (e.g., FIPS-certified security keys). Rejected as out-of-scope for prototype; noted as a future hardening option for regulated deployments.
