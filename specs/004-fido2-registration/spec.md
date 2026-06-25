# Feature Specification: FIDO2 Registration & Chain Enrolment

**Feature Branch**: `004-fido2-registration`

**Created**: 2026-06-25

**Status**: Draft

**Input**: User description: "Feature 004 — FIDO2 registration and chain enrolment, since that's the prerequisite for everything else."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Register a New Identity with a Hardware-Backed Key (Priority: P1)

A user visiting a service for the first time creates a FIDO2 credential (passkey) using their device's hardware security element (biometric sensor, security key, etc.). The credential's public key is submitted to the system for enrolment. Once the required number of validators have co-signed the submission, the identity appears in the trust bundle and can be verified by other services.

**Why this priority**: Without a registered identity, no downstream verification, login, or access flows are possible. This is the root of the entire trust chain.

**Independent Test**: A new identity can be created end-to-end — a credential is generated, submitted, co-signed by validators, and the resulting DID can be verified against a freshly generated trust bundle.

**Acceptance Scenarios**:

1. **Given** a user has no registered identity, **When** they initiate registration on a supported device, **Then** the device prompts for biometric or PIN confirmation and creates a credential without ever exposing the private key.
2. **Given** a credential has been created, **When** the credential's public key is submitted for enrolment, **Then** the system records a pending identity request with the DID and public key.
3. **Given** a pending identity request exists, **When** the minimum required number of validators co-sign it, **Then** the identity is written to the ledger and included in the next trust bundle.
4. **Given** an identity is written to the ledger, **When** a trust bundle is generated, **Then** the identity can be verified using the existing `DecPKIClient.verify()` flow.
5. **Given** fewer validators than the quorum threshold have signed a request, **When** the system checks its status, **Then** the identity remains pending and cannot be used for verification.

---

### User Story 2 - Re-Register on a New Device (Priority: P2)

A user who already has a registered identity wants to add a second device (e.g., a new phone or a hardware security key). They go through a second registration flow that adds a new credential public key to their existing DID, without creating a duplicate identity.

**Why this priority**: Single-device lock-in is a major usability barrier. Users lose devices; hardware fails. Supporting multiple credentials per identity is essential for real-world use.

**Independent Test**: An existing DID can have a second credential public key added; both credentials verify against the same DID in the trust bundle.

**Acceptance Scenarios**:

1. **Given** a user already has a registered DID, **When** they register from a new device, **Then** the new credential's public key is linked to the existing DID rather than creating a new one.
2. **Given** a user has two registered credentials, **When** either device is used to assert identity, **Then** verification succeeds for the same DID.
3. **Given** a user registers from a new device without proving ownership of the existing DID, **Then** the request is rejected — impersonation is not permitted.

---

### User Story 3 - Revoke a Credential (Priority: P3)

A user who has lost a device, or an administrator managing a service identity, can revoke a specific credential. After revocation, that credential's public key can no longer be used to assert the identity, and the change propagates to the trust bundle within the configured revocation lag.

**Why this priority**: Credential compromise is a security-critical scenario. Revocation closes the window after a device is lost or stolen.

**Independent Test**: After a credential is revoked and a new bundle is generated, attempting to verify the DID using the revoked credential fails. An unrevoked credential for the same DID continues to succeed.

**Acceptance Scenarios**:

1. **Given** a credential has been registered, **When** a revocation request is submitted and co-signed by the required validators, **Then** the credential is marked revoked in the ledger.
2. **Given** a credential is revoked, **When** the next trust bundle is generated, **Then** the revoked credential is excluded from the bundle (or included in the revocation set).
3. **Given** a credential is revoked but the bundle has not yet refreshed, **When** verification is attempted offline, **Then** the outcome reflects the current bundle state — the revocation lag is bounded by the bundle validity window (per existing revocation policy).

---

### Edge Cases

- What happens when a user cancels the device prompt mid-registration (dismisses biometric dialog)?
- What happens if the same credential public key is submitted twice for enrolment?
- How does the system handle an enrolment request that never reaches quorum (validators offline, key lost)?
- What happens if a user tries to add a second device without any proof of owning the existing DID?
- How is a DID formatted if it does not yet exist when the credential is first created?

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST allow a user to initiate a credential registration flow from a browser without the private key ever leaving the user's device.
- **FR-002**: On successful credential creation, the system MUST record a pending enrolment request containing the DID, the credential's public key, and metadata (timestamp, device hint).
- **FR-003**: A pending enrolment request MUST only be promoted to an active identity record once the configured validator quorum threshold has co-signed it (minimum 2-of-3).
- **FR-004**: Once an identity is active, it MUST appear in the next generated trust bundle and MUST be verifiable by the existing `DecPKIClient.verify()` API without any changes to that API.
- **FR-005**: The system MUST assign each registered identity a unique DID in the `did:local:` namespace (or the deployment's configured namespace).
- **FR-006**: The system MUST support adding a second credential to an existing DID, provided the requestor can prove ownership of the existing DID or an authorised administrator approves.
- **FR-007**: Revocation of a specific credential MUST be a new ledger record, not a mutation of the existing identity record (per Principle III of the constitution).
- **FR-008**: The system MUST reject duplicate enrolment of the same credential public key.
- **FR-009**: If a pending enrolment request has not reached quorum within a configurable timeout, the system MUST surface its status as `PENDING` and allow re-submission or cancellation.
- **FR-010**: The registration flow MUST be completable on all browsers that support FIDO2/WebAuthn (Chrome 67+, Firefox 60+, Safari 14+, Edge 79+).

### Key Entities

- **CredentialRegistrationRequest**: A pending request containing the DID (or a proposed DID for new users), the credential public key in COSE format, the requesting party's metadata, timestamps, and collected validator signatures.
- **Credential**: A credential public key bound to a DID, with issuance and optional revocation timestamps. A DID may have multiple credentials.
- **IdentityRecord**: Unchanged from Feature 003 — the canonical ledger record for a DID, now potentially referencing multiple credentials.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A new user can complete credential creation and enrolment submission in under 60 seconds on a device with biometric support.
- **SC-002**: After validator co-signing, a newly enrolled identity appears in the trust bundle within one bundle refresh cycle (bounded by the configured bundle validity period).
- **SC-003**: 100% of enrolment requests that do not reach quorum are surfaced with a `PENDING` status — no request silently disappears.
- **SC-004**: Zero credential private keys are transmitted to or stored by any server at any point in the registration flow.
- **SC-005**: A revoked credential is excluded from trust bundles generated after the revocation record is written to the ledger.
- **SC-006**: The existing `DecPKIClient.verify()` API requires no changes to verify identities registered via FIDO2 enrolment.

## Assumptions

- The FIDO2 credential creation (passkey) step happens entirely in the browser; this feature covers the enrolment submission and validator co-signing pipeline, not the browser-side UX scaffolding beyond what is needed to hand off the public key.
- The BFF (Backend-for-Frontend) acts as the submission endpoint — it receives the credential public key from the browser and forwards it to the PKI validator pipeline.
- Validator co-signing in this prototype happens via the existing CLI (`decpki` tool); a future feature may introduce an automated or API-driven signing flow.
- The first registered credential for a user defines their DID; subsequent credentials are linked to that existing DID.
- Proof of ownership for adding a second credential is a signed challenge from an existing, valid credential — not an out-of-band recovery code (this scope keeps the cryptographic model clean; recovery codes are a future concern).
- The existing `IdentityRecord` format (Feature 003 bundle wire format) is extended minimally — the goal is that bundle consumers require no changes.
- Mobile native app support is out of scope; this feature targets browser-based WebAuthn only.
