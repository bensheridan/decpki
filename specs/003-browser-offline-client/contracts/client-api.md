# Contract: DecPKIClient Public API

## Overview

`DecPKIClient` is the main entry point for the browser offline identity client library.
It is instantiated by the consuming application once per page load.

---

## Constructor

```typescript
new DecPKIClient(config: ClientConfig)
```

### ClientConfig

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `bundleEndpoint` | `string` | Yes | — | HTTPS URL where bundle.cbor is served |
| `swPath` | `string` | No | `"/decpki-sw.js"` | URL path where the SW script is hosted |
| `swScope` | `string` | No | `"/"` | Service Worker registration scope |

**Throws**: nothing (sync, safe)

---

## Methods

### `init(): Promise<void>`

Registers the Service Worker, opens IndexedDB, and loads the current bundle into memory.
Must be called before `verify()`. Safe to call multiple times (idempotent).

**Throws**: `UnsupportedBrowserError` if required APIs are unavailable.

---

### `verify(did: string): Promise<VerificationResult>`

Verifies a DID against the locally stored trust bundle. Makes no network calls.

**Parameters**:
- `did` — the W3C DID string to look up (e.g. `"did:local:payments-svc"`)

**Returns**: `VerificationResult`

| Outcome | Condition |
|---------|-----------|
| `VALID` | DID found, Merkle proof verified, bundle not expired |
| `NOT_FOUND` | DID not in bundle |
| `EXPIRED` | `Date.now() / 1000 > bundle.expiresAt` |
| `TAMPERED` | Merkle proof or signature check failed |
| `QUORUM_FAILURE` | Valid signature count < threshold |
| `NO_BUNDLE` | No bundle stored locally |
| `UNSUPPORTED` | Browser lacks required crypto APIs |

**Performance**: < 500ms for bundles up to 10,000 identities.

---

### `getSyncState(): Promise<BundleSyncState | null>`

Returns the current sync state, or `null` if no sync has ever run.

---

### `requestSync(): Promise<void>`

Asks the Service Worker to attempt an immediate bundle refresh. Returns when the sync
request has been delivered to the SW (not when sync completes). The SW broadcasts
`BUNDLE_UPDATED` when a fresh bundle is ready.

---

### `destroy(): void`

Removes the SW message listener. Does not unregister the SW or delete stored data.

---

## Events (BroadcastChannel: `"decpki"`)

The library broadcasts the following events on the `decpki` BroadcastChannel:

| `type` | Payload | When |
|--------|---------|------|
| `BUNDLE_UPDATED` | `{ expiresAt: number }` | SW stored a fresh bundle |
| `SYNC_FAILED` | `{ error: string }` | SW sync attempt failed |

Application code can listen:

```javascript
const ch = new BroadcastChannel('decpki');
ch.onmessage = (e) => {
  if (e.data.type === 'BUNDLE_UPDATED') {
    // re-run verification if needed
  }
};
```

---

## Errors

| Class | When thrown |
|-------|-------------|
| `UnsupportedBrowserError` | `crypto.subtle` or `indexedDB` unavailable |
| `BundleValidationError` | Signature or quorum check failed during sync |

Both extend `Error` and have a `.message` string.

---

## TypeScript Types

```typescript
interface ClientConfig {
  bundleEndpoint: string;
  swPath?: string;
  swScope?: string;
}

interface VerificationResult {
  outcome: Outcome;
  did: string;
  bundleExpiresAt: number | null;
  message: string;
}

type Outcome =
  | 'VALID'
  | 'NOT_FOUND'
  | 'EXPIRED'
  | 'TAMPERED'
  | 'QUORUM_FAILURE'
  | 'NO_BUNDLE'
  | 'UNSUPPORTED';

interface BundleSyncState {
  lastSync: number | null;
  status: 'idle' | 'syncing' | 'failed';
  endpointUrl: string;
  lastError: string | null;
}

class UnsupportedBrowserError extends Error {}
class BundleValidationError extends Error {}
```
