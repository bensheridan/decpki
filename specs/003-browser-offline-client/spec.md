# Feature Specification: Browser Offline Identity Client

**Feature Branch**: `003-browser-offline-client`

**Created**: 2026-06-24

**Status**: Draft

**Input**: User description: "Full feature (Service Worker + IndexedDB) — production-ready offline-first client"

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Verify a Service Identity While Offline (Priority: P1)

A user opens a web application that has previously synced a trust bundle. Their device has no
network connection. The application verifies a service identity locally and displays a clear
trusted / untrusted / expired result — without making any network calls.

**Why this priority**: This is the core value proposition. If verification doesn't work offline,
the feature is not useful. Everything else supports this scenario.

**Independent Test**: Load the web app, sync a trust bundle, disable all network interfaces,
reload the page, trigger a verification — result must appear without any outbound request.
Confirm using browser DevTools Network panel (all requests blocked, verification still succeeds).

**Acceptance Scenarios**:

1. **Given** the app has previously synced a trust bundle and the device is offline, **When** the
   user triggers identity verification for a known DID, **Then** the result (VALID, EXPIRED, or
   NOT FOUND) is displayed within 500ms with no network activity.

2. **Given** the app is offline and the trust bundle has expired, **When** the user triggers
   verification, **Then** the result clearly shows the bundle is expired and indicates when it
   expired, so the user understands they need to sync when back online.

3. **Given** the app has no trust bundle yet (first launch, never synced), **When** the user
   is offline, **Then** the app shows a clear message that a bundle sync is required and
   cannot verify identities.

---

### User Story 2 — Automatic Bundle Sync When Online (Priority: P2)

The trust bundle updates itself in the background when the device is online, without requiring
any manual action from the user. The user is notified when a fresher bundle is available.

**Why this priority**: The offline guarantee is only as good as the bundle's freshness.
Automatic sync is what makes the expiry/revocation model work in practice.

**Independent Test**: With a valid bundle installed, go offline, wait for the bundle to expire,
come back online — within 60 seconds the bundle should be refreshed and verification should
return VALID again.

**Acceptance Scenarios**:

1. **Given** the device comes online and the current bundle is within 80% of its expiry window,
   **When** the background sync runs, **Then** a fresh bundle is fetched and stored, replacing
   the old one, without interrupting the user's current session.

2. **Given** the device is online and the bundle sync completes, **When** the app was open
   during the sync, **Then** the app receives a notification that a newer bundle is available
   and offers to apply it.

3. **Given** the bundle sync fails (server unreachable), **When** the existing bundle has not
   yet expired, **Then** verification continues to work using the existing bundle, and no error
   is shown to the user (silent retry in background).

---

### User Story 3 — Tamper and Quorum Verification (Priority: P3)

The client verifies that the trust bundle was signed by the required number of validators and
that it has not been tampered with — before accepting it as authoritative.

**Why this priority**: Without this check, a man-in-the-middle could serve a forged bundle.
This is the cryptographic safety net that makes the decentralised trust model meaningful in
the browser.

**Independent Test**: Serve a bundle with one byte flipped in a signature, load it in the app —
the app must reject it and display a tamper-detected error. Serve a bundle signed by only one
validator where threshold is two — the app must reject it with a quorum failure message.

**Acceptance Scenarios**:

1. **Given** a trust bundle whose validator signatures have been modified, **When** the app
   loads or syncs this bundle, **Then** the app rejects it with a clear tamper-detected message
   and retains the last known good bundle.

2. **Given** a trust bundle with fewer validator signatures than the required threshold,
   **When** the app attempts to install it, **Then** the app rejects it with a quorum failure
   message and retains the last known good bundle.

3. **Given** a valid bundle followed by a tampered bundle during sync, **When** the sync
   completes, **Then** the app continues using the valid bundle and logs the rejection reason.

---

### Edge Cases

- What if the browser clears storage (user clears site data, private browsing mode)? The app
  must detect the missing bundle gracefully and prompt re-sync, not crash or show stale results.
- What if the bundle is very large (10,000+ identities)? Verification of a single DID must
  remain fast; loading the full bundle into memory on every check must be avoided.
- What if two tabs are open simultaneously and both try to sync? Only one sync should run;
  the second tab should receive the result once complete.
- What if the validator's public key in the bundle has been tampered with alongside the
  signature? The verification chain must still detect this (signature won't verify against
  the modified public key).
- What if the browser does not support the required cryptographic APIs? The app must detect
  this at startup and show a clear compatibility message rather than silently failing.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The client MUST be able to verify a DID against a locally stored trust bundle
  with zero outbound network calls, producing one of: VALID, NOT FOUND, EXPIRED, TAMPERED,
  or QUORUM FAILURE.
- **FR-002**: The client MUST verify all validator signatures in the bundle before accepting
  it as authoritative. A bundle failing signature verification MUST be rejected and the
  previously stored valid bundle MUST be retained.
- **FR-003**: The client MUST verify Merkle inclusion proofs for each identity record before
  reporting VALID, ensuring the record is genuinely part of the signed snapshot.
- **FR-004**: The trust bundle MUST be persisted in local storage so that verification
  works after the browser is closed and reopened, without re-syncing.
- **FR-005**: The client MUST automatically attempt to refresh the bundle in the background
  when online, without requiring user interaction.
- **FR-006**: Bundle refresh MUST be triggered when the device comes online AND when the
  existing bundle has consumed more than 80% of its validity window.
- **FR-007**: If a bundle refresh fails and the existing bundle has not expired, verification
  MUST continue to work normally with no error shown to the user.
- **FR-008**: If no bundle exists (first launch) or the bundle has expired and no refresh is
  possible (offline), the client MUST clearly communicate that verification is unavailable
  and explain why.
- **FR-009**: The client MUST prevent concurrent bundle sync operations — if a sync is already
  in progress, additional sync triggers MUST wait for or reuse the in-progress result.
- **FR-010**: The client MUST detect when the browser lacks required cryptographic capabilities
  and display a compatibility warning at startup rather than producing silent failures.
- **FR-011**: The verification function MUST complete within 500ms for bundles containing up
  to 10,000 identity records on a mid-range device.
- **FR-012**: The client MUST expose a simple callable interface for application code to
  invoke verification by DID and receive a structured result, without exposing internal
  cryptographic or storage details.

### Key Entities

- **TrustBundle** (stored locally): The complete signed bundle received from the bundle
  endpoint — same format as the server-side CBOR bundle, decoded into a structured object
  for local storage. Includes snapshot root, identities with Merkle proofs, validator
  signatures, expiry timestamp, and threshold.
- **VerificationResult**: The output of a verification call — outcome (VALID/NOT_FOUND/
  EXPIRED/TAMPERED/QUORUM_FAILURE), the queried DID, the bundle expiry timestamp, and a
  human-readable message.
- **BundleSyncState**: Tracks the sync lifecycle — last sync timestamp, sync status
  (idle/syncing/failed), and the URL of the bundle endpoint.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Identity verification completes in under 500ms for a bundle of up to 10,000
  identities on a mid-range device, measured from call to result with no network activity.
- **SC-002**: The bundle sync cycle (fetch, validate, store) completes in under 5 seconds
  on a standard broadband connection for a 10,000-identity bundle.
- **SC-003**: After a fresh bundle is stored, the app remains functional through at least one
  full bundle expiry cycle (e.g., 24 hours offline) without requiring re-sync.
- **SC-004**: 100% of tampered or under-quorum bundles presented during sync are rejected;
  0% of valid bundles are incorrectly rejected.
- **SC-005**: The feature works correctly on the three most recent versions of Chrome, Firefox,
  and Safari as of the implementation date, covering at least 95% of desktop browser market share.
- **SC-006**: An application developer can integrate the verification interface into an existing
  web app by following the quickstart guide, with no prior knowledge of the PKI system,
  in under 30 minutes.

## Assumptions

- The trust bundle is served over HTTPS from a known endpoint (URL configured at integration
  time). Bundle endpoint security (TLS) is assumed; the bundle's own cryptographic signatures
  provide integrity independent of transport security.
- The bundle format is the same CBOR binary format produced by the `decpki` server library
  (feature 001). A JavaScript CBOR decoder is included in the client.
- The consuming web application is responsible for deciding when and how to display verification
  results to end users. The client library provides the verification logic and bundle management,
  not the UI.
- Browser support targets the three most recent versions of Chrome, Firefox, and Safari.
  Internet Explorer and legacy Edge are explicitly out of scope.
- The client library is delivered as a JavaScript module (ESM) that the application bundles
  or loads directly. No server-side rendering or Node.js runtime is required.
- Private browsing / incognito mode may limit persistent storage; the client degrades
  gracefully (in-session bundle only, no persistence) rather than failing entirely.
- The bundle endpoint returns the bundle as a binary response. No authentication is required
  to fetch the bundle (it is a public trust artifact, like a certificate chain).
- Multi-tab coordination (preventing duplicate sync operations) is handled at the library
  level; the application does not need to manage this.
