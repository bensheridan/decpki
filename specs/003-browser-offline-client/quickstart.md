# Quickstart Validation Guide: Browser Offline Identity Client

This guide describes how to validate the feature end-to-end once implementation is complete.
It assumes you have the Python `decpki` CLI available (feature 001) to generate test bundles.

---

## Prerequisites

- Node.js 18+ and npm
- Python `decpki` CLI installed (`pip install -e .` from repo root)
- A modern browser (Chrome 113+, Firefox 129+, or Safari 17+)

---

## Step 1: Build the library

```bash
cd browser/
npm install
npm run build
# Produces: dist/decpki-client.mjs, dist/decpki-client.iife.js, dist/decpki-sw.js
```

---

## Step 2: Generate a test bundle

```bash
# Generate 3 validator keypairs
decpki keygen --name alpha --out /tmp/alpha.key.json
decpki keygen --name beta  --out /tmp/beta.key.json
decpki keygen --name gamma --out /tmp/gamma.key.json

# Register a test identity
decpki register \
  --did did:local:test-service \
  --pubkey /tmp/alpha.key.json \
  --validator /tmp/alpha.key.json \
  --validator /tmp/beta.key.json

# Bundle with 30-minute expiry (for testing)
decpki bundle \
  --validator /tmp/alpha.key.json \
  --validator /tmp/beta.key.json \
  --validator /tmp/gamma.key.json \
  --threshold 2 \
  --grace 30m \
  --out /tmp/bundle.cbor
```

---

## Step 3: Serve the bundle and demo page

```bash
# From browser/ directory
npm run dev
# Starts a local HTTP server at http://localhost:3000
# Serves /tmp/bundle.cbor at http://localhost:3000/bundle.cbor
# Serves dist/ at http://localhost:3000/
# Serves the demo HTML at http://localhost:3000/demo.html
```

---

## Validation Scenario 1: Offline Verification (P1)

**Goal**: Verify `did:local:test-service` works with network disabled.

1. Open `http://localhost:3000/demo.html` in browser
2. Click **Sync Bundle** — status should show "Bundle synced, expires in ~30 min"
3. Open DevTools → Network tab → set throttle to **Offline**
4. Click **Verify** for `did:local:test-service`
5. Expected result: `VALID` badge, no network requests in DevTools
6. Reload the page (still offline)
7. Click **Verify** again — result must still be `VALID`

**Pass criteria**: `outcome === "VALID"`, zero network requests, result within 500ms.

---

## Validation Scenario 2: Auto Sync on Reconnect (P2)

**Goal**: Bundle refreshes automatically when device comes back online.

1. Generate a bundle with `--grace 30s` (30-second expiry grace)
2. Sync the bundle (see Scenario 1, step 1-2)
3. Set DevTools to **Offline**
4. Wait 35 seconds (bundle expires)
5. Click **Verify** — expected result: `EXPIRED`
6. Set DevTools back to **Online** (re-enables network)
7. Wait up to 60 seconds — status should update to "Bundle synced"
8. Click **Verify** — expected result: `VALID`

**Pass criteria**: Bundle refreshes automatically without user clicking Sync; verify returns
`VALID` after refresh.

---

## Validation Scenario 3: Tamper Detection (P3)

**Goal**: A tampered bundle is rejected; the old bundle is retained.

1. Sync a valid bundle (Scenario 1)
2. Flip one byte in `/tmp/bundle.cbor` using a hex editor or:
   ```bash
   python3 -c "
   data = bytearray(open('/tmp/bundle.cbor','rb').read())
   data[10] ^= 0xFF
   open('/tmp/bundle-tampered.cbor','wb').write(data)
   "
   ```
3. Point the server to serve `bundle-tampered.cbor`
4. Click **Sync Bundle** in the demo page
5. Expected: error message "Bundle validation failed: tampered or under-quorum"
6. Click **Verify** — expected result: `VALID` (old bundle still active)

**Pass criteria**: Tampered bundle rejected; old bundle untouched; verify still returns `VALID`.

---

## Validation Scenario 4: First Launch (No Bundle)

**Goal**: Clear state gives a clear "no bundle" message, not a crash.

1. Open browser DevTools → Application → IndexedDB → delete `decpki` database
2. Reload the page
3. Expected: status shows "No trust bundle. Go online and click Sync."
4. Click **Verify** — expected result: `NO_BUNDLE` with explanation

**Pass criteria**: No crash, clear user-facing message, `outcome === "NO_BUNDLE"`.

---

## Validation Scenario 5: Multi-tab Sync Coordination

**Goal**: Two tabs don't trigger duplicate syncs.

1. Open `http://localhost:3000/demo.html` in two tabs
2. Click **Sync Bundle** in both tabs simultaneously
3. Check server access logs — bundle should be fetched exactly once
4. Both tabs should show updated bundle status

**Pass criteria**: Bundle endpoint receives exactly 1 request during concurrent sync.

---

## Validation Scenario 6: Unsupported Browser

**Goal**: Graceful degradation when Web Crypto unavailable.

1. In DevTools console, temporarily override `window.crypto`:
   ```javascript
   Object.defineProperty(window, 'crypto', { value: undefined });
   ```
2. Reload and call `client.init()`
3. Expected: `UnsupportedBrowserError` thrown, compatibility warning shown

**Pass criteria**: Error thrown synchronously during init; no silent failures.

---

## Unit Test Validation

Run all unit tests:

```bash
cd browser/
npm test
# Expects: all tests pass, covering crypto, Merkle verification, CBOR decode, IDB operations
```

Run Playwright browser tests (requires browser binaries):

```bash
npm run test:e2e
# Runs Scenarios 1-4 in headless Chrome automatically
```

---

## Bundle Size Check

```bash
npm run build
ls -lh dist/
# decpki-client.mjs   — must be < 30KB gzipped
# decpki-sw.js        — must be < 15KB gzipped
gzip -c dist/decpki-client.mjs | wc -c
gzip -c dist/decpki-sw.js | wc -c
```
