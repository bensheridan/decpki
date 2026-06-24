# Research: Browser Offline Identity Client

## Decision 1: Ed25519 Signature Verification

**Decision**: `crypto.subtle.verify()` with `{ name: "Ed25519" }` algorithm as primary path;
`@noble/ed25519` (~8KB, pure JS, audited by Trail of Bits) as feature-detected fallback for
browsers without native Ed25519 support.

**Rationale**: Native Web Crypto is ~10× faster than pure-JS and has no supply chain surface.
`@noble/ed25519` covers the gap for Safari < 17 and Firefox < 129, giving us the full target
browser matrix. Detection: `crypto.subtle.importKey("raw", ..., "Ed25519", false, ["verify"])`
— if it throws `NotSupportedError`, fall back to noble.

**Alternatives considered**:
- `libsodium-wrappers` (WASM): 300KB+, too heavy for a library.
- `tweetnacl`: No active maintenance, smaller community than noble.
- Native-only (drop older browsers): Would exclude Safari 15/16, a significant share.

---

## Decision 2: CBOR Decoding

**Decision**: `cbor-x` — ESM build, ~12KB minified+gzipped.

**Rationale**: Best performance benchmark in the browser, tree-shakeable, actively maintained,
supports `decode()` for one-shot binary parsing of the bundle. The bundle is decoded once on
sync and stored as a plain JS object in IndexedDB — no re-decoding on verify.

**Alternatives considered**:
- `cbor-web` (by the RFC author): Correct but larger and slower.
- `cborg`: Good but slightly heavier API for this use case.

---

## Decision 3: Persistent Storage

**Decision**: IndexedDB via the `idb` wrapper library (~2KB minified+gzipped).

**Database name**: `decpki`
**Object stores**:
  - `bundles` — key: `"current"`, value: decoded bundle object
  - `meta` — key: `"sync"`, value: `{ lastSync, status, endpointUrl }`

**Rationale**: `localStorage` is synchronous (blocks main thread), limited to 5MB strings, and
cannot store binary data without base64 encoding. A 10,000-identity bundle is ~1MB binary. IndexedDB
supports async reads, binary blobs, and survives browser restarts. The `idb` wrapper reduces the
boilerplate from ~50 lines to ~5 lines per operation.

**Private browsing**: IndexedDB is available in private browsing but data is not persisted across
sessions. The library detects this by catching `InvalidStateError` on DB open and falls back to
an in-memory cache for the session.

**Alternatives considered**:
- Cache API (Service Worker cache): Designed for HTTP responses, not structured data; awkward
  for binary objects.
- OPFS (Origin Private File System): Very new, not in all target browsers, overkill for one file.

---

## Decision 4: Background Sync Strategy

**Decision**: Service Worker with `online` event listener + refresh check on SW `activate`.
No dependency on `SyncManager` (Background Sync API).

**Why not SyncManager**: Background Sync is Chrome-only. Safari and Firefox do not support it.

**Sync trigger conditions** (either triggers a refresh attempt):
1. SW `activate` event fires (page load, SW update, browser restart)
2. SW receives `online` message from the main thread (forwarded from `window` online event)
3. 80% of bundle validity window has elapsed: `now > issued_at + 0.8 * (expires_at - issued_at)`

**Multi-tab coordination**: SW is the single sync authority. All open tabs communicate with the
SW via `postMessage`. When a fresh bundle is stored, the SW broadcasts `{ type: "BUNDLE_UPDATED" }`
to all clients via `self.clients.matchAll()`. Tabs update their in-memory reference on receipt.

**Concurrent sync prevention**: A module-level `syncInProgress` boolean in the SW. If true,
incoming sync requests are queued and receive the result of the in-progress sync.

---

## Decision 5: Module Delivery

**Decision**: Single-file ESM module (`decpki-client.mjs`) built with `esbuild`. Also ship
an IIFE build (`decpki-client.iife.js`) for pages that don't use modules. Separate
`decpki-sw.js` for the Service Worker (must be a separate file, cannot be an ES module
in all browsers).

**Bundle sizes (targets)**:
- `decpki-client.mjs`: < 30KB minified+gzipped (includes cbor-x + idb + noble fallback)
- `decpki-sw.js`: < 15KB minified+gzipped

**Rationale**: esbuild is the fastest JS bundler, produces clean output, and requires no
configuration file for single-entry-point builds.

---

## Decision 6: SHA-256 for Merkle Proofs

**Decision**: `crypto.subtle.digest('SHA-256', buffer)` — native, async, available in all
target browsers.

**Merkle verification algorithm** (JS port of Python `verify_proof`):
```
leaf_hash = SHA256(0x00 || leaf_bytes)
for each {h, s} in siblings:
    if s == "left":  current = SHA256(0x01 || h || current)
    else:            current = SHA256(0x01 || current || h)
assert current == root
```
Buffer concatenation via `Uint8Array` and `TextEncoder`. All async — wrapped in a single
`verifyProof(leafBytes, siblings, root)` async function.

---

## Decision 7: Public API Shape

```typescript
// Main entry point (loaded by application)
import { DecPKIClient } from './decpki-client.mjs';

const client = new DecPKIClient({
  bundleEndpoint: 'https://your-server.example/bundle.cbor',
  swPath: '/decpki-sw.js',          // path where decpki-sw.js is served
});

await client.init();                  // registers SW, loads bundle from IndexedDB

const result = await client.verify('did:local:payments-svc');
// result: { outcome, did, bundleExpiresAt, message }
```

The `DecPKIClient` constructor is synchronous; `init()` is async (registers SW + warms cache).
`verify()` is always async (IndexedDB reads + Web Crypto are async).

---

## Summary: Resolved Technical Context

| Field              | Value |
|--------------------|-------|
| Language/Version   | JavaScript (ES2022), TypeScript types included |
| Primary Dependencies | `cbor-x` (CBOR decode), `idb` (IndexedDB), `@noble/ed25519` (fallback crypto) |
| Storage            | IndexedDB (`decpki` DB, `bundles` + `meta` stores) |
| Testing            | Vitest + jsdom (unit); Playwright (browser integration) |
| Target Platform    | Browser — Chrome 113+, Firefox 129+, Safari 17+ (with noble fallback for older) |
| Project Type       | Client-side library (ESM + IIFE builds) + Service Worker |
| Performance Goals  | verify() < 500ms for 10k-identity bundle; bundle sync < 5s on broadband |
| Constraints        | No server-side runtime; no build toolchain required by consumers |
| Scale/Scope        | Single-page app integration; up to 10k identities per bundle |
