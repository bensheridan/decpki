# decpki-client

Browser offline identity client for the decentralised PKI prototype.

Verifies W3C DID identities against a locally-stored trust bundle with **zero network calls** during verification. A Service Worker handles background bundle sync.

## Browser support

| Browser | Min version | Ed25519 |
|---------|-------------|---------|
| Chrome  | 113+        | native  |
| Firefox | 129+        | native  |
| Safari  | 17+         | native  |
| Older   | —           | @noble/ed25519 fallback |

## Quickstart

```html
<!-- 1. Copy dist/decpki-sw.js to your web root -->
<!-- 2. Load the IIFE bundle -->
<script src="/decpki-client.iife.js"></script>
<script>
  const client = new DecPKILib.DecPKIClient({
    bundleEndpoint: 'https://your-server.example/bundle.cbor',
    swPath: '/decpki-sw.js',
  });

  // Init once per page load
  await client.init();

  // Verify a DID — works offline once a bundle is synced
  const result = await client.verify('did:local:payments-svc');
  // result.outcome: 'VALID' | 'NOT_FOUND' | 'EXPIRED' | 'TAMPERED' | 'QUORUM_FAILURE' | 'NO_BUNDLE'
  console.log(result.outcome, result.message);

  // Listen for auto-sync updates
  client.onBundleUpdated = ({ expiresAt }) => {
    console.log('Fresh bundle synced, expires', new Date(expiresAt * 1000));
  };
</script>
```

## ESM import

```js
import { DecPKIClient } from './decpki-client.mjs';

const client = new DecPKIClient({ bundleEndpoint: '/bundle.cbor' });
await client.init();
const result = await client.verify('did:local:api-gateway');
```

## API reference

See [`src/index.d.ts`](src/index.d.ts) for full TypeScript types.

| Method | Returns | Description |
|--------|---------|-------------|
| `new DecPKIClient(config)` | `DecPKIClient` | Create client; `config.bundleEndpoint` required |
| `client.init()` | `Promise<void>` | Register SW, open IndexedDB, load bundle |
| `client.verify(did)` | `Promise<VerificationResult>` | Verify DID offline; < 500ms |
| `client.getSyncState()` | `Promise<BundleSyncState\|null>` | Current sync status |
| `client.requestSync()` | `Promise<void>` | Ask SW for immediate sync |
| `client.destroy()` | `void` | Clean up listeners |

## Outcomes

| `outcome` | Meaning |
|-----------|---------|
| `VALID` | DID found, all proofs pass, bundle not expired |
| `NOT_FOUND` | DID not in bundle |
| `EXPIRED` | Bundle has passed `expiresAt` |
| `TAMPERED` | Merkle proof failed (bundle integrity issue) |
| `QUORUM_FAILURE` | Bundle has fewer valid signatures than threshold |
| `NO_BUNDLE` | No bundle stored; sync first |
| `UNSUPPORTED` | Browser lacks required crypto APIs |

## Bundle sync

The Service Worker automatically syncs when:
- The SW activates (page load / restart)
- The device comes online (`window` online event)
- The bundle has consumed > 80% of its validity window

Multiple tabs share a single sync; duplicates are suppressed.

## Running the demo

The demo requires a real browser tab (not a preview panel) — Service Workers need an HTTP origin.

**Step 1: Generate a test bundle** (from the repo root)

```bash
decpki keygen --name alpha --out /tmp/alpha.key.json
decpki keygen --name beta  --out /tmp/beta.key.json
decpki keygen --name gamma --out /tmp/gamma.key.json

PUBKEY=$(python3 -c "import json; d=json.load(open('/tmp/alpha.key.json')); print(d['public_key'])")

decpki register \
  --did did:local:test-svc \
  --pubkey "$PUBKEY" \
  --validator /tmp/alpha.key.json \
  --validator /tmp/beta.key.json

decpki bundle \
  --validator /tmp/alpha.key.json \
  --validator /tmp/beta.key.json \
  --validator /tmp/gamma.key.json \
  --threshold 2 \
  --grace 24h \
  --out /tmp/bundle.cbor
```

**Step 2: Build the JS library**

```bash
cd browser
npm install
npm run build
```

**Step 3: Start the dev server**

```bash
cd browser
BUNDLE_PATH=/tmp/bundle.cbor node demo/server.mjs
# → http://localhost:3000
```

Open **http://localhost:3000** in your browser. Then:

1. Click **Sync Bundle** — fetches `bundle.cbor` via the Service Worker
2. Type `did:local:test-svc` in the input and click **Verify** — shows `VALID`
3. Open DevTools → Network → set throttle to **Offline**
4. Click **Verify** again — still `VALID` with zero network requests

To test expiry: use `--grace 30s` in the bundle command, sync, wait 31 seconds, verify — shows `EXPIRED`.

## Build

```bash
npm install
npm run build   # → dist/decpki-client.mjs, dist/decpki-client.iife.js, dist/decpki-sw.js
npm test        # unit tests (Vitest + happy-dom)
```

## Validation

See [`../specs/003-browser-offline-client/quickstart.md`](../specs/003-browser-offline-client/quickstart.md) for 6 end-to-end validation scenarios.
