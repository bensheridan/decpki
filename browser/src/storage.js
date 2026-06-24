import { openDB } from 'idb';

const DB_NAME = 'decpki';
const DB_VERSION = 1;

// In-memory fallback for private browsing / unsupported environments
const memStore = new Map();
let useMemory = false;

async function getDb() {
  if (useMemory) return null;
  try {
    return await openDB(DB_NAME, DB_VERSION, {
      upgrade(db) {
        if (!db.objectStoreNames.contains('bundles')) db.createObjectStore('bundles');
        if (!db.objectStoreNames.contains('meta')) db.createObjectStore('meta');
      },
    });
  } catch (e) {
    // Private browsing or storage not available
    useMemory = true;
    return null;
  }
}

export async function saveBundle(bundle) {
  const db = await getDb();
  if (!db) { memStore.set('bundle:current', bundle); return; }
  await db.put('bundles', bundle, 'current');
}

export async function loadBundle() {
  const db = await getDb();
  if (!db) return memStore.get('bundle:current') ?? null;
  return (await db.get('bundles', 'current')) ?? null;
}

export async function saveSyncState(state) {
  const db = await getDb();
  if (!db) { memStore.set('meta:sync', state); return; }
  await db.put('meta', state, 'sync');
}

export async function loadSyncState() {
  const db = await getDb();
  if (!db) return memStore.get('meta:sync') ?? null;
  return (await db.get('meta', 'sync')) ?? null;
}
