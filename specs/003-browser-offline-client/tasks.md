# Tasks: Browser Offline Identity Client

**Input**: Design documents from `specs/003-browser-offline-client/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/client-api.md, contracts/sw-messages.md

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to
- Paths are relative to `browser/` unless noted

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Initialize the `browser/` project directory and build tooling.

- [X] T001 Create `browser/` directory structure per plan.md (src/, sw/, demo/, tests/unit/, tests/e2e/, dist/)
- [X] T002 Create `browser/package.json` with dependencies: `cbor-x`, `idb`, `@noble/ed25519`; devDeps: `esbuild`, `vitest`, `jsdom`, `@vitest/coverage-v8`
- [X] T003 [P] Create `browser/build.mjs` esbuild script that produces `dist/decpki-client.mjs` (ESM), `dist/decpki-client.iife.js` (IIFE), and copies `sw/decpki-sw.js` to `dist/decpki-sw.js`
- [X] T004 [P] Create `browser/.gitignore` covering `node_modules/`, `dist/`, `*.log`, `.env*`
- [X] T005 [P] Add `vitest.config.js` to `browser/` with jsdom environment for unit tests

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core cryptographic primitives and storage layer used by all user stories.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [X] T006 Create `browser/src/errors.js` with `UnsupportedBrowserError` and `BundleValidationError` classes (both extend Error)
- [X] T007 Create `browser/src/crypto.js` with: `detectEd25519Support()` (feature-detects native Web Crypto Ed25519), `verifyEd25519(publicKeyBytes, message, signatureBytes)` (native path with noble fallback), `sha256(data)` (returns Uint8Array via `crypto.subtle.digest`), `hashLeaf(leafBytes)` (SHA256(0x00 || leafBytes)), `hashNode(left, right)` (SHA256(0x01 || left || right))
- [X] T008 Create `browser/src/crypto.js` addition: `verifyMerkleProof(leafBytes, siblings, rootBytes)` async function that walks the proof from leaf to root using hashLeaf/hashNode per data-model.md SiblingNode spec
- [X] T009 Create `browser/src/storage.js` with: `openDb()` (opens `decpki` IndexedDB v1 with `bundles` + `meta` stores), `saveBundle(bundle)`, `loadBundle()`, `saveSyncState(state)`, `loadSyncState()` — all returning Promises, using `idb` wrapper; handle `InvalidStateError` (private browsing) by falling back to an in-memory Map
- [X] T010 Create `browser/src/bundle.js` with: `decodeBundle(arrayBuffer)` (uses `cbor-x` to decode CBOR, maps short field names to full JS object per data-model.md TrustBundle), `validateBundle(bundle)` (checks fmtVer, expiresAt, threshold, verifies all signatures against the canonical bundle payload using `crypto.js`; throws `BundleValidationError` on any failure)
- [X] T011 Create `browser/tests/unit/crypto.test.js` with unit tests: SHA-256 produces correct 32-byte output, hashLeaf prepends 0x00, hashNode prepends 0x01, verifyMerkleProof returns true for a known-good proof, returns false for a tampered sibling
- [X] T012 Create `browser/tests/unit/storage.test.js` with unit tests: saveBundle/loadBundle round-trip, saveSyncState/loadSyncState round-trip, loadBundle returns null when no bundle stored

**Checkpoint**: `npm test` in `browser/` passes for crypto and storage unit tests. Foundation is ready.

---

## Phase 3: User Story 1 — Offline Verification (Priority: P1) 🎯 MVP

**Goal**: A user can verify a DID from a locally stored bundle with zero network calls.

**Independent Test**: Sync a bundle, disable network in DevTools, reload, verify — result must appear within 500ms with no outbound requests (see quickstart.md Scenario 1).

### Implementation for User Story 1

- [X] T013 [US1] Create `browser/src/index.js` with `DecPKIClient` class: constructor accepts `ClientConfig` (bundleEndpoint, swPath, swScope), stores config, initializes null bundle reference
- [X] T014 [US1] Implement `DecPKIClient.init()` in `browser/src/index.js`: detects unsupported browser (throws `UnsupportedBrowserError` if `crypto.subtle` or `indexedDB` unavailable), registers Service Worker at `swPath`, opens IndexedDB via `storage.js`, loads current bundle from IndexedDB into memory
- [X] T015 [US1] Implement `DecPKIClient.verify(did)` in `browser/src/index.js`: returns `VerificationResult` with NO_BUNDLE if no bundle loaded; EXPIRED if `Date.now()/1000 > bundle.expiresAt`; searches `bundle.identities` for matching DID; NOT_FOUND if absent; calls `verifyMerkleProof` for the matching entry; returns VALID or TAMPERED based on proof result; completes in < 500ms
- [X] T016 [US1] Create `browser/tests/unit/verify.test.js` with unit tests for `verify()`: returns NO_BUNDLE when no bundle loaded, EXPIRED when bundle past expiresAt, NOT_FOUND for unknown DID, VALID for a known DID with a valid Merkle proof (use a synthetic minimal bundle fixture), TAMPERED when proof sibling is mutated
- [X] T017 [US1] Create `browser/demo/index.html` with a minimal demo page: input field for DID, Sync button, Verify button, result display area; loads `decpki-client.iife.js` and `decpki-sw.js`; calls `client.init()` on load
- [X] T018 [US1] Create `browser/demo/server.mjs` — minimal Node.js HTTP server that serves `dist/` at `/`, serves a bundle file (path configurable via `BUNDLE_PATH` env var) at `/bundle.cbor`, default port 3000
- [X] T019 [US1] Run `npm install && npm run build` in `browser/` and verify `dist/decpki-client.mjs` and `dist/decpki-client.iife.js` are produced; verify gzipped size < 30KB

**Checkpoint**: Manual validation of quickstart.md Scenario 1 passes. `verify()` returns VALID with DevTools offline.

---

## Phase 4: User Story 2 — Automatic Bundle Sync (Priority: P2)

**Goal**: The bundle refreshes automatically in the background when online; the app is notified when a fresh bundle is available.

**Independent Test**: Sync a bundle, let it expire (use `--grace 30s`), reconnect — within 60 seconds verify returns VALID again (see quickstart.md Scenario 2).

### Implementation for User Story 2

- [X] T020 [US2] Create `browser/sw/decpki-sw.js` Service Worker: import `cbor-x` (IIFE build), define `syncInProgress` flag, implement `doSync(endpointUrl)` async function — fetches bundle.cbor, calls `validateBundle`, stores via `storage.js`, broadcasts `BUNDLE_UPDATED` on success or `SYNC_FAILED` on error; broadcasts are sent via `BroadcastChannel("decpki")`
- [X] T021 [US2] Add SW `activate` event handler in `browser/sw/decpki-sw.js`: calls `self.clients.claim()`, then loads stored sync state and runs `doSync()` if bundle is within 80% expiry window (`now > issuedAt + 0.8 * (expiresAt - issuedAt)`)
- [X] T022 [US2] Add SW `message` event handler in `browser/sw/decpki-sw.js`: handles `SYNC_REQUEST` (sends `SYNC_ACK` to requesting client, calls `doSync()` if not already in progress) and `GET_BUNDLE_STATUS` (reads IDB and replies with `BUNDLE_STATUS` message) per contracts/sw-messages.md
- [X] T023 [US2] Implement `DecPKIClient.requestSync()` in `browser/src/index.js`: posts `SYNC_REQUEST` to the registered SW via `navigator.serviceWorker.controller.postMessage`; no-op if SW not registered
- [X] T024 [US2] Implement `DecPKIClient.getSyncState()` in `browser/src/index.js`: reads `BundleSyncState` from IndexedDB via `storage.js`
- [X] T025 [US2] Add `window` online event forwarding in `browser/src/index.js` `init()`: when `window` fires `online`, call `requestSync()`
- [X] T026 [US2] Add BroadcastChannel listener in `browser/src/index.js` `init()`: listens on `"decpki"` channel; on `BUNDLE_UPDATED`, reloads bundle from IDB into memory; exposes `onBundleUpdated` callback on the client instance
- [X] T027 [US2] Update `browser/demo/index.html`: show sync status, last sync timestamp, and a listener for `BUNDLE_UPDATED` that updates the status display without requiring a page reload
- [X] T028 [US2] Implement `DecPKIClient.destroy()` in `browser/src/index.js`: closes the BroadcastChannel, removes the `online` event listener

**Checkpoint**: Manual validation of quickstart.md Scenario 2 passes. Bundle auto-refreshes after coming online; UI updates without reload.

---

## Phase 5: User Story 3 — Tamper and Quorum Verification (Priority: P3)

**Goal**: Tampered or under-quorum bundles are rejected; the last good bundle is retained.

**Independent Test**: Serve a bundle with a flipped byte — the app rejects it and verify still returns VALID using the old bundle (see quickstart.md Scenario 3).

### Implementation for User Story 3

- [X] T029 [US3] Extend `validateBundle()` in `browser/src/bundle.js`: verify each validator signature against the canonical payload (CBOR re-encoded with `signatures: []`); count valid signatures; throw `BundleValidationError("quorum")` if valid count < threshold; throw `BundleValidationError("tampered")` if any signature fails verification
- [X] T030 [US3] Update `doSync()` in `browser/sw/decpki-sw.js`: wrap `validateBundle()` call in try/catch; on `BundleValidationError`, do NOT overwrite the stored bundle; broadcast `SYNC_FAILED` with the error message; save failed sync state to IDB (`status: "failed"`, `lastError: error.message`)
- [X] T031 [US3] Add QUORUM_FAILURE outcome to `DecPKIClient.verify()` in `browser/src/index.js`: if the in-memory bundle's `validSignatureCount < threshold` (computed at load time by `validateBundle`), return `{ outcome: "QUORUM_FAILURE", ... }`
- [X] T032 [US3] Add TAMPERED outcome to `DecPKIClient.verify()` in `browser/src/index.js`: if `verifyMerkleProof` returns false for the matched identity entry, return `{ outcome: "TAMPERED", ... }`
- [X] T033 [US3] Create `browser/tests/unit/bundle.test.js` with unit tests: `validateBundle` throws `BundleValidationError` for tampered signature (one byte flipped), throws for under-quorum bundle, accepts valid bundle, rejects future format version (fmtVer != 1)
- [X] T034 [US3] Update `browser/demo/index.html`: display tamper/quorum error messages in the UI when sync fails

**Checkpoint**: Manual validation of quickstart.md Scenario 3 passes. Tampered bundle rejected; old bundle still serves VALID.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Type declarations, bundle size verification, edge case hardening.

- [X] T035 [P] Create `browser/src/index.d.ts` TypeScript declaration file for `DecPKIClient`, `ClientConfig`, `VerificationResult`, `Outcome`, `BundleSyncState`, `UnsupportedBrowserError`, `BundleValidationError` per contracts/client-api.md
- [X] T036 [P] Verify gzipped bundle sizes: `gzip -c dist/decpki-client.mjs | wc -c` < 30720 bytes; `gzip -c dist/decpki-sw.js | wc -c` < 15360 bytes; adjust esbuild config in `build.mjs` if needed
- [X] T037 Run full unit test suite (`npm test` in `browser/`) and confirm all tests pass
- [X] T038 Add `"decpki"` BroadcastChannel cleanup to `destroy()` in `browser/src/index.js` if not already present; verify no listener leaks across multiple `init()`/`destroy()` cycles
- [X] T039 [P] Add `browser/README.md` with: quickstart integration snippet, API reference summary, browser support table, link to quickstart.md for full validation scenarios
- [X] T040 Run all 6 quickstart.md validation scenarios manually and confirm each passes

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: No dependencies — start immediately
- **Phase 2 (Foundational)**: Depends on Phase 1 — BLOCKS all user stories
- **Phase 3 (US1 — Offline Verify)**: Depends on Phase 2 — no dependency on US2/US3
- **Phase 4 (US2 — Auto Sync)**: Depends on Phase 2; integrates with US1 client class
- **Phase 5 (US3 — Tamper Detection)**: Depends on Phase 2; extends US2's `doSync()` and US1's `verify()`
- **Phase 6 (Polish)**: Depends on Phases 3, 4, 5 all complete

### Within Each Phase

- T007 before T008 (sha256/hashLeaf before verifyMerkleProof)
- T013 before T014, T014 before T015 (class skeleton before methods)
- T020 before T021, T021 before T022 (SW foundation before event handlers)
- T029 before T030 (validateBundle extension before SW integration)

### Parallel Opportunities

- T003, T004, T005 — all setup tasks, different files
- T011, T012 — unit test files, different files
- T035, T036, T039 — polish tasks, different files

---

## Parallel Example: Phase 2 (Foundational)

```
# Can run in parallel:
Task T006: browser/src/errors.js
Task T007+T008: browser/src/crypto.js

# Then in parallel (after T007/T008):
Task T009: browser/src/storage.js
Task T010: browser/src/bundle.js

# Then in parallel (after T009/T010):
Task T011: browser/tests/unit/crypto.test.js
Task T012: browser/tests/unit/storage.test.js
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (CRITICAL — blocks all stories)
3. Complete Phase 3: User Story 1 (offline verify)
4. **STOP and VALIDATE**: Run quickstart.md Scenario 1 manually
5. Demo to stakeholders — core offline guarantee is proved

### Incremental Delivery

1. Setup + Foundational → build passes, unit tests green
2. User Story 1 → verify() works offline — **MVP demo ready**
3. User Story 2 → auto-sync works → complete offline-first lifecycle
4. User Story 3 → tamper detection → cryptographic safety net complete
5. Polish → types, size checks, README

### Notes

- [P] tasks have no file conflicts — safe to parallelize
- Each user story phase ends with a verifiable checkpoint from quickstart.md
- `decpki-sw.js` must be built as a standalone IIFE (Service Workers cannot be ES modules in all target browsers)
- The `cbor-x` import inside the SW requires the IIFE/CJS build of cbor-x, not the ESM build — ensure `build.mjs` bundles the SW separately with the correct cbor-x entry point
