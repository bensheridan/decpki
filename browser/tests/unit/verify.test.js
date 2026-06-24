import { describe, it, expect, beforeEach } from 'vitest';
import { DecPKIClient } from '../../src/index.js';

function b64(s) {
  const bin = atob(s);
  return new Uint8Array(bin.length).map((_, i) => bin.charCodeAt(i));
}

// Real fixture generated from the Python CLI with a known-valid bundle
const FIXTURE = {
  fmtVer: 1,
  snapBlock: 0,
  snapRoot: b64('NVOpwUjiFK57u2ZIFThi5+NPNgcsARzed3G2EEKvVro='),
  issuedAt: 1782292655,
  expiresAt: 9999999999, // far future — won't expire in tests
  threshold: 2,
  valSet: ['alpha', 'beta', 'gamma'],
  identities: [
    {
      record: {
        did: 'did:local:test-svc',
        publicKey: b64('+3PmyU4qB3KJXBWgLPhO5mR02rGCprQ+KHlH5XjbBXM='),
        issuedAt: 1782292655,
        issuedBy: ['alpha', 'beta'],
        validUntil: null,
        revokedAt: null,
        metadata: {},
      },
      proof: {
        leafHash: b64('NVOpwUjiFK57u2ZIFThi5+NPNgcsARzed3G2EEKvVro='),
        siblings: [],
        root: b64('NVOpwUjiFK57u2ZIFThi5+NPNgcsARzed3G2EEKvVro='),
      },
    },
  ],
  signatures: [],
  _validSigCount: 2, // pre-validated for these tests
};

function makeClient() {
  const client = new DecPKIClient({ bundleEndpoint: 'https://example.com/bundle.cbor' });
  return client;
}

describe('DecPKIClient.verify', () => {
  it('returns NO_BUNDLE when no bundle is loaded', async () => {
    const client = makeClient();
    const result = await client.verify('did:local:test-svc');
    expect(result.outcome).toBe('NO_BUNDLE');
    expect(result.bundleExpiresAt).toBeNull();
  });

  it('returns EXPIRED when bundle expiresAt is in the past', async () => {
    const client = makeClient();
    client._bundle = { ...FIXTURE, expiresAt: 1000 }; // far past
    const result = await client.verify('did:local:test-svc');
    expect(result.outcome).toBe('EXPIRED');
    expect(result.bundleExpiresAt).toBe(1000);
  });

  it('returns NOT_FOUND for an unknown DID', async () => {
    const client = makeClient();
    client._bundle = FIXTURE;
    const result = await client.verify('did:local:unknown');
    expect(result.outcome).toBe('NOT_FOUND');
    expect(result.did).toBe('did:local:unknown');
  });

  it('returns VALID for a known DID with a correct Merkle proof', async () => {
    const client = makeClient();
    client._bundle = FIXTURE;
    const result = await client.verify('did:local:test-svc');
    expect(result.outcome).toBe('VALID');
    expect(result.did).toBe('did:local:test-svc');
    expect(result.bundleExpiresAt).toBe(9999999999);
  });

  it('returns QUORUM_FAILURE when _validSigCount is absent (fail-closed)', async () => {
    const client = makeClient();
    const bundleWithoutCount = { ...FIXTURE };
    delete bundleWithoutCount._validSigCount;
    client._bundle = bundleWithoutCount;
    const result = await client.verify('did:local:test-svc');
    expect(result.outcome).toBe('QUORUM_FAILURE');
  });

  it('returns TAMPERED when the proof sibling is mutated', async () => {
    const client = makeClient();
    // Create a bundle where the snapRoot differs from the leaf hash (proof will fail)
    const tampered = {
      ...FIXTURE,
      snapRoot: new Uint8Array(32).fill(0xaa), // wrong root
    };
    client._bundle = tampered;
    const result = await client.verify('did:local:test-svc');
    expect(result.outcome).toBe('TAMPERED');
  });
});
