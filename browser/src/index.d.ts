export interface ClientConfig {
  bundleEndpoint: string;
  swPath?: string;
  swScope?: string;
}

export type Outcome =
  | 'VALID'
  | 'NOT_FOUND'
  | 'EXPIRED'
  | 'TAMPERED'
  | 'QUORUM_FAILURE'
  | 'NO_BUNDLE'
  | 'UNSUPPORTED';

export interface VerificationResult {
  outcome: Outcome;
  did: string;
  bundleExpiresAt: number | null;
  message: string;
}

export interface BundleSyncState {
  lastSync: number | null;
  status: 'idle' | 'syncing' | 'failed';
  endpointUrl: string;
  lastError: string | null;
  lastBundleExpiresAt?: number;
}

export declare class UnsupportedBrowserError extends Error {
  constructor(message?: string);
}

export declare class BundleValidationError extends Error {
  reason: string;
  constructor(reason: string, message?: string);
}

export declare class DecPKIClient {
  onBundleUpdated: ((event: { expiresAt: number }) => void) | null;

  constructor(config: ClientConfig);

  init(): Promise<void>;
  verify(did: string): Promise<VerificationResult>;
  getSyncState(): Promise<BundleSyncState | null>;
  requestSync(): Promise<void>;
  destroy(): void;
}
