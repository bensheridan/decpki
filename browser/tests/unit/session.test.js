import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import {
  DecPKISession,
  LoginCancelledError,
  LoginFailedError,
  DIDNotFoundError,
  SessionExpiredError,
} from '../../src/session.js';

vi.mock('@simplewebauthn/browser', () => ({
  startAuthentication: vi.fn(),
}));

import { startAuthentication } from '@simplewebauthn/browser';

// Minimal localStorage shim for jsdom
const LS = {};
const localStorageMock = {
  getItem: (k) => LS[k] ?? null,
  setItem: (k, v) => { LS[k] = String(v); },
  removeItem: (k) => { delete LS[k]; },
  clear: () => { Object.keys(LS).forEach(k => delete LS[k]); },
};
vi.stubGlobal('localStorage', localStorageMock);
vi.stubGlobal('fetch', vi.fn());

const START_RESP = {
  challenge: 'abc123',
  allow_credentials: [{ type: 'public-key', id: 'cred-id' }],
  user_verification: 'preferred',
  timeout: 60000,
};

const ASSERTION = { id: 'cred-id', response: { authenticatorData: 'x', clientDataJSON: 'y', signature: 'z' } };

const COMPLETE_RESP = {
  session_token: 'tok.abc.def',
  refresh_token: 'ff'.repeat(32),
  did: 'did:local:test',
  expires_at: Math.floor(Date.now() / 1000) + 900,
  refresh_expires_at: Math.floor(Date.now() / 1000) + 604800,
};

function makeSession() {
  return new DecPKISession({ bffBaseUrl: 'http://localhost:8000/login' });
}

function mockFetchSequence(...responses) {
  let i = 0;
  fetch.mockImplementation(() => {
    const resp = responses[i++] || responses[responses.length - 1];
    return Promise.resolve(resp);
  });
}

function jsonResp(body, status = 200) {
  return { ok: status >= 200 && status < 300, status, json: () => Promise.resolve(body) };
}

beforeEach(() => {
  localStorageMock.clear();
  vi.clearAllMocks();
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe('DecPKISession constructor', () => {
  it('accepts localhost URLs', () => {
    expect(() => new DecPKISession({ bffBaseUrl: 'http://localhost:8000/login' })).not.toThrow();
  });

  it('accepts https URLs', () => {
    expect(() => new DecPKISession({ bffBaseUrl: 'https://example.com/login' })).not.toThrow();
  });

  it('rejects non-localhost http URLs', () => {
    expect(() => new DecPKISession({ bffBaseUrl: 'http://example.com/login' })).toThrow();
  });
});

describe('login()', () => {
  it('stores tokens in localStorage on success', async () => {
    mockFetchSequence(jsonResp(START_RESP), jsonResp(COMPLETE_RESP));
    startAuthentication.mockResolvedValue(ASSERTION);

    const session = makeSession();
    const result = await session.login('did:local:test');

    expect(result.did).toBe('did:local:test');
    expect(localStorage.getItem('decpki_session')).toBe('tok.abc.def');
    expect(localStorage.getItem('decpki_did')).toBe('did:local:test');
    expect(localStorage.getItem('decpki_refresh')).toBe('ff'.repeat(32));
  });

  it('throws LoginCancelledError on NotAllowedError', async () => {
    mockFetchSequence(jsonResp(START_RESP));
    const err = new Error('Not allowed'); err.name = 'NotAllowedError';
    startAuthentication.mockRejectedValue(err);

    const session = makeSession();
    await expect(session.login('did:local:test')).rejects.toBeInstanceOf(LoginCancelledError);
  });

  it('throws DIDNotFoundError on BFF 404', async () => {
    mockFetchSequence(jsonResp({}, 404));
    const session = makeSession();
    await expect(session.login('did:local:missing')).rejects.toBeInstanceOf(DIDNotFoundError);
  });

  it('throws LoginFailedError on BFF 401 at complete', async () => {
    mockFetchSequence(jsonResp(START_RESP), jsonResp({ detail: 'bad sig' }, 401));
    startAuthentication.mockResolvedValue(ASSERTION);
    const session = makeSession();
    await expect(session.login('did:local:test')).rejects.toBeInstanceOf(LoginFailedError);
  });
});

describe('isLoggedIn()', () => {
  it('returns false with no token', () => {
    expect(makeSession().isLoggedIn()).toBe(false);
  });

  it('returns true when token and future expiry stored', () => {
    localStorage.setItem('decpki_session', 'tok');
    localStorage.setItem('decpki_expires_at', String(Math.floor(Date.now() / 1000) + 900));
    expect(makeSession().isLoggedIn()).toBe(true);
  });

  it('returns false when token expired', () => {
    localStorage.setItem('decpki_session', 'tok');
    localStorage.setItem('decpki_expires_at', String(Math.floor(Date.now() / 1000) - 1));
    expect(makeSession().isLoggedIn()).toBe(false);
  });
});

describe('getToken()', () => {
  it('returns null when not logged in', async () => {
    expect(await makeSession().getToken()).toBeNull();
  });

  it('returns token when session valid', async () => {
    localStorage.setItem('decpki_session', 'good-token');
    localStorage.setItem('decpki_expires_at', String(Math.floor(Date.now() / 1000) + 900));
    expect(await makeSession().getToken()).toBe('good-token');
  });

  it('triggers refresh() when expiry within 120s', async () => {
    localStorage.setItem('decpki_session', 'old-token');
    localStorage.setItem('decpki_refresh', 'refresh-tok');
    localStorage.setItem('decpki_expires_at', String(Math.floor(Date.now() / 1000) + 60));

    const refreshResp = { session_token: 'new-token', did: 'did:local:test', expires_at: Math.floor(Date.now() / 1000) + 900 };
    mockFetchSequence(jsonResp(refreshResp));

    const session = makeSession();
    const tok = await session.getToken();
    expect(tok).toBe('new-token');
  });
});

describe('logout()', () => {
  it('clears localStorage and calls POST /logout', async () => {
    localStorage.setItem('decpki_session', 'tok');
    localStorage.setItem('decpki_refresh', 'ref-tok');
    localStorage.setItem('decpki_did', 'did:local:test');
    localStorage.setItem('decpki_expires_at', '9999999999');

    fetch.mockResolvedValue(jsonResp({ ok: true }));

    const session = makeSession();
    await session.logout();

    expect(localStorage.getItem('decpki_session')).toBeNull();
    expect(localStorage.getItem('decpki_refresh')).toBeNull();
    expect(fetch).toHaveBeenCalledWith(
      expect.stringContaining('/logout'),
      expect.objectContaining({ method: 'POST' }),
    );
  });
});
