// DecPKI Service Worker — bundle sync coordinator
// Built as IIFE by esbuild; cannot use top-level await or ESM syntax here.

import { decode } from 'cbor-x';
import { encodeCbor } from '../src/cbor-canonical.js';
import { openDB } from 'idb';
import { verifyEd25519 } from '../src/crypto.js';
import { BundleValidationError } from '../src/errors.js';

const DB_NAME = 'decpki';
const DB_VERSION = 1;
const BROADCAST_CHANNEL = 'decpki';
const CURRENT_FORMAT_VERSION = 1;
const SYNC_THRESHOLD = 0.8;

let syncInProgress = false;
const channel = new BroadcastChannel(BROADCAST_CHANNEL);

// ─── IndexedDB helpers ────────────────────────────────────────────────────────

async function getDb() {
  return openDB(DB_NAME, DB_VERSION, {
    upgrade(db) {
      if (!db.objectStoreNames.contains('bundles')) db.createObjectStore('bundles');
      if (!db.objectStoreNames.contains('meta')) db.createObjectStore('meta');
    },
  });
}

async function saveBundle(bundle) {
  const db = await getDb();
  await db.put('bundles', bundle, 'current');
}

async function loadBundle() {
  const db = await getDb();
  return (await db.get('bundles', 'current')) ?? null;
}

async function saveSyncState(state) {
  const db = await getDb();
  await db.put('meta', state, 'sync');
}

async function loadSyncState() {
  const db = await getDb();
  return (await db.get('meta', 'sync')) ?? null;
}

// ─── Bundle decode & validate ─────────────────────────────────────────────────

function toUint8(v) {
  if (v instanceof Uint8Array) return v;
  if (Array.isArray(v)) return new Uint8Array(v);
  return v;
}

function decodeBundle(arrayBuffer) {
  const raw = new Uint8Array(arrayBuffer);
  const m = decode(raw);

  if (m.fmt_ver !== CURRENT_FORMAT_VERSION) {
    throw new BundleValidationError('version', `Unknown format version: ${m.fmt_ver}`);
  }

  const identities = (m.identities || []).map((entry) => ({
    record: {
      did: entry.did,
      publicKey: toUint8(entry.pubkey),
      issuedAt: entry.issued_at,
      issuedBy: entry.issued_by,
      validUntil: entry.valid_until ?? null,
      revokedAt: entry.revoked_at ?? null,
      metadata: entry.meta || {},
    },
    proof: {
      leafHash: toUint8(entry.proof.leaf),
      siblings: (entry.proof.siblings || []).map((s) => ({ h: toUint8(s.h), s: s.s })),
      root: toUint8(entry.proof.root),
    },
  }));

  const signatures = (m.signatures || []).map((sig) => ({
    validatorDid: sig.val_did,
    validatorPubkey: toUint8(sig.val_pk),
    signature: toUint8(sig.sig),
  }));

  return {
    fmtVer: m.fmt_ver,
    snapBlock: m.snap_block,
    snapRoot: toUint8(m.snap_root),
    issuedAt: m.issued_at,
    expiresAt: m.expires_at,
    threshold: m.threshold,
    valSet: m.val_set || [],
    identities,
    signatures,
  };
}

function buildSigningPayload(bundle) {
  const identitiesCbor = bundle.identities.map((entry) => ({
    did: entry.record.did,
    issued_at: entry.record.issuedAt,
    issued_by: entry.record.issuedBy,
    meta: entry.record.metadata,
    proof: {
      leaf: entry.proof.leafHash,
      root: entry.proof.root,
      siblings: entry.proof.siblings.map((s) => ({ h: s.h, s: s.s })),
    },
    pubkey: entry.record.publicKey,
    revoked_at: entry.record.revokedAt,
    valid_until: entry.record.validUntil,
  }));

  return encodeCbor({
    expires_at: bundle.expiresAt,
    fmt_ver: bundle.fmtVer,
    identities: identitiesCbor,
    issued_at: bundle.issuedAt,
    signatures: [],
    snap_block: bundle.snapBlock,
    snap_root: bundle.snapRoot,
    threshold: bundle.threshold,
    val_set: bundle.valSet,
  });
}

async function validateBundle(bundle) {
  if (bundle.fmtVer !== CURRENT_FORMAT_VERSION) {
    throw new BundleValidationError('version');
  }

  const now = Math.floor(Date.now() / 1000);
  if (bundle.expiresAt <= now) {
    throw new BundleValidationError('expired', 'Bundle has already expired');
  }

  const signingPayload = buildSigningPayload(bundle);
  let validSigCount = 0;
  for (const sig of bundle.signatures) {
    const ok = await verifyEd25519(sig.validatorPubkey, signingPayload, sig.signature);
    if (ok) validSigCount++;
  }

  if (validSigCount < bundle.threshold) {
    throw new BundleValidationError(
      'quorum',
      `Quorum failure: ${validSigCount} valid signatures, need ${bundle.threshold}`
    );
  }

  bundle._validSigCount = validSigCount;
  return bundle;
}

// ─── Sync ─────────────────────────────────────────────────────────────────────

async function doSync(endpointUrl) {
  if (syncInProgress) return;
  syncInProgress = true;

  try {
    const response = await fetch(endpointUrl);
    if (!response.ok) throw new Error(`HTTP ${response.status}: ${response.statusText}`);

    const arrayBuffer = await response.arrayBuffer();
    const bundle = decodeBundle(arrayBuffer);
    await validateBundle(bundle);

    await saveBundle(bundle);
    await saveSyncState({
      lastSync: Date.now(),
      status: 'idle',
      endpointUrl,
      lastError: null,
      lastBundleExpiresAt: bundle.expiresAt,
    });

    channel.postMessage({ type: 'BUNDLE_UPDATED', expiresAt: bundle.expiresAt });
  } catch (e) {
    await saveSyncState({
      lastSync: null,
      status: 'failed',
      endpointUrl,
      lastError: e.message,
    });
    channel.postMessage({ type: 'SYNC_FAILED', error: e.message });
  } finally {
    syncInProgress = false;
  }
}

async function maybeSyncOnActivate() {
  const state = await loadSyncState();
  if (!state?.endpointUrl) return;

  const bundle = await loadBundle();
  if (!bundle) {
    await doSync(state.endpointUrl);
    return;
  }

  // Sync if within 80% of validity window
  const windowLength = bundle.expiresAt - bundle.issuedAt;
  const elapsed = Math.floor(Date.now() / 1000) - bundle.issuedAt;
  if (elapsed > SYNC_THRESHOLD * windowLength) {
    await doSync(state.endpointUrl);
  }
}

// ─── SW Event Handlers ────────────────────────────────────────────────────────

self.addEventListener('install', () => self.skipWaiting());

self.addEventListener('activate', (event) => {
  event.waitUntil(
    self.clients.claim().then(() => maybeSyncOnActivate())
  );
});

self.addEventListener('message', (event) => {
  const { type } = event.data || {};

  if (type === 'SYNC_REQUEST') {
    if (event.source) event.source.postMessage({ type: 'SYNC_ACK' });
    loadSyncState().then((state) => {
      if (state?.endpointUrl) doSync(state.endpointUrl);
    });
    return;
  }

  if (type === 'GET_BUNDLE_STATUS') {
    loadBundle().then(async (bundle) => {
      const state = await loadSyncState();
      const now = Math.floor(Date.now() / 1000);
      event.source?.postMessage({
        type: 'BUNDLE_STATUS',
        expiresAt: bundle?.expiresAt ?? null,
        isExpired: bundle ? now > bundle.expiresAt : true,
        syncStatus: state?.status ?? 'idle',
        lastSync: state?.lastSync ?? null,
      });
    });
    return;
  }

  if (type === 'ONLINE') {
    loadSyncState().then((state) => {
      if (state?.endpointUrl) doSync(state.endpointUrl);
    });
  }
});
