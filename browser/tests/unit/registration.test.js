import { describe, it, expect, vi, beforeEach } from 'vitest';
import {
  DecPKIRegistration,
  RegistrationCancelledError,
  AlgorithmNotSupportedError,
  OwnershipProofFailedError,
  RegistrationError,
} from '../../src/registration.js';

vi.mock('@simplewebauthn/browser', () => ({
  startRegistration: vi.fn(),
  startAuthentication: vi.fn(),
}));

const START_RESPONSE = {
  challenge: 'abc123',
  rp: { name: 'DecPKI', id: 'localhost' },
  user: { id: 'dXNlcg', name: 'user', displayName: 'User' },
  pubKeyCredParams: [{ type: 'public-key', alg: -8 }],
  timeout: 60000,
  attestation: 'none',
  request_type: 'new',
  pending_did: 'did:local:test-uuid',
};

const SUBMIT_RESPONSE = {
  request_id: 'req-uuid',
  did: 'did:local:test-uuid',
  status: 'pending',
  signatures_collected: 0,
  threshold: 2,
  expires_at: 9999999999,
};

const CREDENTIAL = { id: 'cred-id', rawId: 'cred-id', type: 'public-key', response: {} };

function mockFetch(responses) {
  let i = 0;
  global.fetch = vi.fn(async () => responses[i++]);
}

function jsonResponse(data, status = 200) {
  return { ok: status < 400, status, json: async () => data };
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe('DecPKIRegistration constructor', () => {
  it('throws if bffBaseUrl is missing', () => {
    expect(() => new DecPKIRegistration({})).toThrow('bffBaseUrl');
  });

  it('throws if bffBaseUrl is http:// (non-localhost)', () => {
    expect(() => new DecPKIRegistration({ bffBaseUrl: 'http://example.com' })).toThrow('HTTPS');
  });

  it('allows http://localhost', () => {
    expect(() => new DecPKIRegistration({ bffBaseUrl: 'http://localhost:8000' })).not.toThrow();
  });

  it('allows https://', () => {
    expect(() => new DecPKIRegistration({ bffBaseUrl: 'https://bff.example.com' })).not.toThrow();
  });
});

describe('DecPKIRegistration.register()', () => {
  it('returns RegistrationResult on success', async () => {
    const { startRegistration } = await import('@simplewebauthn/browser');
    startRegistration.mockResolvedValue(CREDENTIAL);
    mockFetch([jsonResponse(START_RESPONSE), jsonResponse(SUBMIT_RESPONSE, 201)]);

    const reg = new DecPKIRegistration({ bffBaseUrl: 'http://localhost:8000/enrolment' });
    const result = await reg.register();

    expect(result.requestId).toBe('req-uuid');
    expect(result.did).toBe('did:local:test-uuid');
    expect(result.status).toBe('pending');
    expect(result.threshold).toBe(2);
  });

  it('throws RegistrationCancelledError when user dismisses prompt', async () => {
    const { startRegistration } = await import('@simplewebauthn/browser');
    const err = new Error('User cancelled');
    err.name = 'NotAllowedError';
    startRegistration.mockRejectedValue(err);
    mockFetch([jsonResponse(START_RESPONSE)]);

    const reg = new DecPKIRegistration({ bffBaseUrl: 'http://localhost:8000/enrolment' });
    await expect(reg.register()).rejects.toBeInstanceOf(RegistrationCancelledError);
  });

  it('throws AlgorithmNotSupportedError on BFF 422 with unsupported algorithm message', async () => {
    const { startRegistration } = await import('@simplewebauthn/browser');
    startRegistration.mockResolvedValue(CREDENTIAL);
    mockFetch([
      jsonResponse(START_RESPONSE),
      jsonResponse({ detail: 'Unsupported COSE algorithm: -257.' }, 422),
    ]);

    const reg = new DecPKIRegistration({ bffBaseUrl: 'http://localhost:8000/enrolment' });
    await expect(reg.register()).rejects.toBeInstanceOf(AlgorithmNotSupportedError);
  });

  it('throws RegistrationError on BFF 409 (duplicate credential)', async () => {
    const { startRegistration } = await import('@simplewebauthn/browser');
    startRegistration.mockResolvedValue(CREDENTIAL);
    mockFetch([
      jsonResponse(START_RESPONSE),
      jsonResponse({ detail: 'Credential ID already registered.' }, 409),
    ]);

    const reg = new DecPKIRegistration({ bffBaseUrl: 'http://localhost:8000/enrolment' });
    await expect(reg.register()).rejects.toBeInstanceOf(RegistrationError);
  });
});

describe('DecPKIRegistration.getStatus()', () => {
  it('returns status for a known request', async () => {
    mockFetch([jsonResponse({ request_id: 'req-uuid', did: 'did:local:x', status: 'pending', signatures_collected: 1, threshold: 2, expires_at: 9999 })]);
    const reg = new DecPKIRegistration({ bffBaseUrl: 'http://localhost:8000/enrolment' });
    const s = await reg.getStatus('req-uuid');
    expect(s.status).toBe('pending');
    expect(s.signaturesCollected).toBe(1);
  });

  it('throws RegistrationError on 404', async () => {
    mockFetch([{ ok: false, status: 404, json: async () => ({}) }]);
    const reg = new DecPKIRegistration({ bffBaseUrl: 'http://localhost:8000/enrolment' });
    await expect(reg.getStatus('not-found')).rejects.toBeInstanceOf(RegistrationError);
  });
});
