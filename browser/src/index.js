import { loadBundle, saveBundle, loadSyncState, saveSyncState } from './storage.js';
import { decodeBundle, validateBundle } from './bundle.js';
import { verifyMerkleProofFromHash } from './crypto.js';
import { UnsupportedBrowserError } from './errors.js';

const BROADCAST_CHANNEL = 'decpki';
const SYNC_THRESHOLD = 0.8;

export class DecPKIClient {
  constructor(config) {
    if (!config || !config.bundleEndpoint) {
      throw new Error('DecPKIClient requires config.bundleEndpoint');
    }
    const endpoint = config.bundleEndpoint;
    if (!endpoint.startsWith('https://') && !endpoint.startsWith('http://localhost') && !endpoint.startsWith('http://127.0.0.1')) {
      throw new Error('bundleEndpoint must use HTTPS (http:// is only permitted for localhost)');
    }
    this._config = {
      bundleEndpoint: endpoint,
      swPath: config.swPath || '/decpki-sw.js',
      swScope: config.swScope || '/',
    };
    this._bundle = null;
    this._sw = null;
    this._channel = null;
    this._onlineHandler = null;
    this.onBundleUpdated = null;
  }

  async init() {
    if (typeof crypto === 'undefined' || !crypto.subtle) {
      throw new UnsupportedBrowserError();
    }
    if (typeof indexedDB === 'undefined') {
      throw new UnsupportedBrowserError('Browser lacks IndexedDB support');
    }

    // Register Service Worker
    if ('serviceWorker' in navigator) {
      try {
        const reg = await navigator.serviceWorker.register(this._config.swPath, {
          scope: this._config.swScope,
        });
        this._sw = reg;
      } catch (e) {
        // SW registration failure is non-fatal — fallback to in-tab sync
        console.warn('[DecPKI] SW registration failed:', e.message);
      }
    }

    // Load bundle from IndexedDB
    const stored = await loadBundle();
    if (stored) this._bundle = stored;

    // Save endpoint URL to sync state if not already set
    const syncState = await loadSyncState();
    if (!syncState || syncState.endpointUrl !== this._config.bundleEndpoint) {
      await saveSyncState({
        lastSync: syncState?.lastSync ?? null,
        status: 'idle',
        endpointUrl: this._config.bundleEndpoint,
        lastError: null,
      });
    }

    // Forward online events to SW
    this._onlineHandler = () => this.requestSync();
    window.addEventListener('online', this._onlineHandler);

    // Listen for bundle updates from SW
    this._channel = new BroadcastChannel(BROADCAST_CHANNEL);
    this._channel.onmessage = async (e) => {
      if (e.data?.type === 'BUNDLE_UPDATED') {
        const fresh = await loadBundle();
        if (fresh) this._bundle = fresh;
        if (typeof this.onBundleUpdated === 'function') {
          this.onBundleUpdated({ expiresAt: e.data.expiresAt });
        }
      }
    };
  }

  async verify(did) {
    const now = Math.floor(Date.now() / 1000);

    if (!this._bundle) {
      return {
        outcome: 'NO_BUNDLE',
        did,
        bundleExpiresAt: null,
        message: 'No trust bundle stored. Go online and sync to continue.',
      };
    }

    const bundle = this._bundle;

    if (now > bundle.expiresAt) {
      return {
        outcome: 'EXPIRED',
        did,
        bundleExpiresAt: bundle.expiresAt,
        message: `Bundle expired at ${new Date(bundle.expiresAt * 1000).toISOString()}. Sync when online to refresh.`,
      };
    }

    // Quorum check — fail closed if _validSigCount is missing (unknown = untrusted)
    const validSigCount = typeof bundle._validSigCount === 'number' ? bundle._validSigCount : -1;
    if (validSigCount < bundle.threshold) {
      return {
        outcome: 'QUORUM_FAILURE',
        did,
        bundleExpiresAt: bundle.expiresAt,
        message: `Bundle has insufficient validator signatures (${validSigCount < 0 ? 'unknown' : validSigCount} of ${bundle.threshold} required).`,
      };
    }

    const entry = bundle.identities.find((e) => e.record.did === did);
    if (!entry) {
      return {
        outcome: 'NOT_FOUND',
        did,
        bundleExpiresAt: bundle.expiresAt,
        message: `Identity '${did}' not found in trust bundle.`,
      };
    }

    const { proof } = entry;
    // Use the pre-computed leafHash from the proof (trusted: covered by validator signatures).
    // This avoids re-encoding the record in CBOR, which would require bit-perfect canonical CBOR.
    const proofValid = await verifyMerkleProofFromHash(proof.leafHash, proof.siblings, bundle.snapRoot);

    if (!proofValid) {
      return {
        outcome: 'TAMPERED',
        did,
        bundleExpiresAt: bundle.expiresAt,
        message: `Merkle proof verification failed for '${did}'. Bundle may have been tampered.`,
      };
    }

    return {
      outcome: 'VALID',
      did,
      bundleExpiresAt: bundle.expiresAt,
      message: `Identity '${did}' verified successfully.`,
    };
  }

  async getSyncState() {
    return loadSyncState();
  }

  async requestSync() {
    if (!navigator.serviceWorker?.controller) return;
    navigator.serviceWorker.controller.postMessage({ type: 'SYNC_REQUEST' });
  }

  destroy() {
    if (this._onlineHandler) {
      window.removeEventListener('online', this._onlineHandler);
      this._onlineHandler = null;
    }
    if (this._channel) {
      this._channel.close();
      this._channel = null;
    }
  }
}

