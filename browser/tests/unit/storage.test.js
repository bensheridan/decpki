import { describe, it, expect, beforeEach } from 'vitest';

// Storage uses IndexedDB via idb. In jsdom, IndexedDB is not available, so
// the module falls back to in-memory storage. We reset the module between tests.
let saveBundle, loadBundle, saveSyncState, loadSyncState;

beforeEach(async () => {
  // Reset module to clear in-memory store between tests
  const mod = await import('../../src/storage.js?t=' + Date.now());
  saveBundle = mod.saveBundle;
  loadBundle = mod.loadBundle;
  saveSyncState = mod.saveSyncState;
  loadSyncState = mod.loadSyncState;
});

describe('bundle storage', () => {
  it('loadBundle returns null when nothing stored', async () => {
    expect(await loadBundle()).toBeNull();
  });

  it('saveBundle and loadBundle round-trip', async () => {
    const bundle = { fmtVer: 1, expiresAt: 9999999999, identities: [] };
    await saveBundle(bundle);
    const loaded = await loadBundle();
    expect(loaded).toEqual(bundle);
  });

  it('saveBundle overwrites previous bundle', async () => {
    await saveBundle({ fmtVer: 1, expiresAt: 1000 });
    await saveBundle({ fmtVer: 1, expiresAt: 2000 });
    const loaded = await loadBundle();
    expect(loaded.expiresAt).toBe(2000);
  });
});

describe('sync state storage', () => {
  it('loadSyncState returns null when nothing stored', async () => {
    expect(await loadSyncState()).toBeNull();
  });

  it('saveSyncState and loadSyncState round-trip', async () => {
    const state = {
      lastSync: 1700000000000,
      status: 'idle',
      endpointUrl: 'https://example.com/bundle.cbor',
      lastError: null,
    };
    await saveSyncState(state);
    const loaded = await loadSyncState();
    expect(loaded).toEqual(state);
  });
});
