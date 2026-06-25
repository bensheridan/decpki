import { describe, it, expect, vi, beforeEach } from 'vitest';
import {
  DecPKISessions,
  SessionsAuthError,
  SessionNotFoundError,
  AddDeviceCancelledError,
  AddDeviceError,
} from '../../src/sessions.js';

// Mock registration module
vi.mock('../../src/registration.js', () => ({
  DecPKIRegistration: vi.fn(),
  RegistrationCancelledError: class RegistrationCancelledError extends Error {
    constructor() { super('cancelled'); this.name = 'RegistrationCancelledError'; }
  },
  RegistrationError: class RegistrationError extends Error {
    constructor(msg) { super(msg); this.name = 'RegistrationError'; }
  },
}));

import { DecPKIRegistration, RegistrationCancelledError } from '../../src/registration.js';

// Minimal localStorage shim
const LS = {};
const localStorageMock = {
  getItem: (k) => LS[k] ?? null,
  setItem: (k, v) => { LS[k] = String(v); },
  removeItem: (k) => { delete LS[k]; },
  clear: () => { Object.keys(LS).forEach(k => delete LS[k]); },
};
vi.stubGlobal('localStorage', localStorageMock);
vi.stubGlobal('fetch', vi.fn());

const mockSession = {
  getToken: vi.fn().mockResolvedValue('mock-token'),
  getDid: vi.fn().mockReturnValue('did:local:test-123'),
};

const BASE = 'http://localhost:8000';

function makeSessions() {
  return new DecPKISessions({ bffBaseUrl: BASE, session: mockSession });
}

const SAMPLE_SESSIONS_RESP = {
  sessions: [
    {
      session_id: 'abcd1234abcd1234',
      did: 'did:local:test-123',
      issued_at: 1700000000,
      expires_at: 1700604800,
      is_current: true,
    },
    {
      session_id: '1111222233334444',
      did: 'did:local:test-123',
      issued_at: 1700001000,
      expires_at: 1700604800,
      is_current: false,
    },
  ],
};

beforeEach(() => {
  vi.clearAllMocks();
  Object.keys(LS).forEach(k => delete LS[k]);
  LS['decpki_refresh'] = 'abcd1234abcd1234xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx';
  mockSession.getToken.mockResolvedValue('mock-token');
  mockSession.getDid.mockReturnValue('did:local:test-123');
});

describe('DecPKISessions constructor', () => {
  it('throws without bffBaseUrl', () => {
    expect(() => new DecPKISessions({ session: mockSession })).toThrow('bffBaseUrl is required');
  });

  it('throws without session', () => {
    expect(() => new DecPKISessions({ bffBaseUrl: BASE })).toThrow('session is required');
  });

  it('accepts localhost', () => {
    expect(() => makeSessions()).not.toThrow();
  });
});

describe('DecPKISessions.list()', () => {
  it('returns SessionEntry[] on success', async () => {
    fetch.mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => SAMPLE_SESSIONS_RESP,
    });
    const s = makeSessions();
    const result = await s.list();
    expect(result.sessions).toHaveLength(2);
    expect(result.sessions[0].sessionId).toBe('abcd1234abcd1234');
    expect(result.sessions[0].isCurrent).toBe(true);
    expect(result.sessions[1].sessionId).toBe('1111222233334444');
    expect(result.sessions[1].isCurrent).toBe(false);
  });

  it('throws SessionsAuthError on 401', async () => {
    fetch.mockResolvedValueOnce({ ok: false, status: 401, json: async () => ({}) });
    const s = makeSessions();
    await expect(s.list()).rejects.toBeInstanceOf(SessionsAuthError);
  });

  it('throws SessionsAuthError when getToken returns null', async () => {
    mockSession.getToken.mockResolvedValue(null);
    const s = makeSessions();
    await expect(s.list()).rejects.toBeInstanceOf(SessionsAuthError);
  });

  it('sends Authorization header', async () => {
    fetch.mockResolvedValueOnce({ ok: true, status: 200, json: async () => ({ sessions: [] }) });
    const s = makeSessions();
    await s.list();
    expect(fetch).toHaveBeenCalledWith(
      `${BASE}/api/sessions`,
      expect.objectContaining({
        headers: expect.objectContaining({ 'Authorization': 'Bearer mock-token' }),
      }),
    );
  });

  it('sends refresh token in body', async () => {
    fetch.mockResolvedValueOnce({ ok: true, status: 200, json: async () => ({ sessions: [] }) });
    const s = makeSessions();
    await s.list();
    const call = fetch.mock.calls[0][1];
    const body = JSON.parse(call.body);
    expect(body.refresh_token).toBe(LS['decpki_refresh']);
  });
});

describe('DecPKISessions.revoke()', () => {
  it('returns { ok, selfRevoked } on success', async () => {
    fetch.mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => ({ ok: true, self_revoked: true }),
    });
    const s = makeSessions();
    const result = await s.revoke('abcd1234abcd1234');
    expect(result.ok).toBe(true);
    expect(result.selfRevoked).toBe(true);
  });

  it('returns selfRevoked: false for non-current session', async () => {
    fetch.mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => ({ ok: true, self_revoked: false }),
    });
    const s = makeSessions();
    const result = await s.revoke('1111222233334444');
    expect(result.selfRevoked).toBe(false);
  });

  it('throws SessionsAuthError on 401', async () => {
    fetch.mockResolvedValueOnce({ ok: false, status: 401, json: async () => ({}) });
    const s = makeSessions();
    await expect(s.revoke('abcd1234abcd1234')).rejects.toBeInstanceOf(SessionsAuthError);
  });

  it('throws SessionNotFoundError on 404', async () => {
    fetch.mockResolvedValueOnce({ ok: false, status: 404, json: async () => ({}) });
    const s = makeSessions();
    await expect(s.revoke('0000000000000000')).rejects.toBeInstanceOf(SessionNotFoundError);
  });
});

describe('DecPKISessions.addDevice()', () => {
  it('returns result on success', async () => {
    const mockResult = { requestId: 'req-1', did: 'did:local:test-123', status: 'pending', threshold: 2, signaturesCollected: 0 };
    const mockAddCredential = vi.fn().mockResolvedValue(mockResult);
    DecPKIRegistration.mockImplementation(() => ({ addCredential: mockAddCredential }));

    const s = makeSessions();
    const result = await s.addDevice();
    expect(result).toEqual(mockResult);
    expect(mockAddCredential).toHaveBeenCalledWith('did:local:test-123');
  });

  it('throws AddDeviceCancelledError on RegistrationCancelledError', async () => {
    DecPKIRegistration.mockImplementation(() => ({
      addCredential: vi.fn().mockRejectedValue(new RegistrationCancelledError()),
    }));
    const s = makeSessions();
    await expect(s.addDevice()).rejects.toBeInstanceOf(AddDeviceCancelledError);
  });

  it('throws AddDeviceError on other registration errors', async () => {
    DecPKIRegistration.mockImplementation(() => ({
      addCredential: vi.fn().mockRejectedValue(new Error('Device not supported')),
    }));
    const s = makeSessions();
    await expect(s.addDevice()).rejects.toBeInstanceOf(AddDeviceError);
  });

  it('throws AddDeviceError when not logged in', async () => {
    mockSession.getDid.mockReturnValue(null);
    const s = makeSessions();
    await expect(s.addDevice()).rejects.toBeInstanceOf(AddDeviceError);
  });
});
