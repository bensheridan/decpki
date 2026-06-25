/**
 * DecPKISession — WebAuthn login, JWT session management, silent refresh.
 */
import { startAuthentication } from '@simplewebauthn/browser';

export class LoginCancelledError extends Error {
  constructor(msg = 'Login cancelled') { super(msg); this.name = 'LoginCancelledError'; }
}
export class LoginFailedError extends Error {
  constructor(msg = 'Login failed') { super(msg); this.name = 'LoginFailedError'; }
}
export class DIDNotFoundError extends Error {
  constructor(msg = 'DID not found') { super(msg); this.name = 'DIDNotFoundError'; }
}
export class SessionExpiredError extends Error {
  constructor(msg = 'Session expired') { super(msg); this.name = 'SessionExpiredError'; }
}

const LS_SESSION   = 'decpki_session';
const LS_REFRESH   = 'decpki_refresh';
const LS_DID       = 'decpki_did';
const LS_EXPIRES   = 'decpki_expires_at';
const REFRESH_BEFORE_SECS = 120;

export class DecPKISession {
  /**
   * @param {{ bffBaseUrl: string }} opts  bffBaseUrl must end without a trailing slash,
   *   e.g. 'http://localhost:8000/login'
   */
  constructor({ bffBaseUrl }) {
    if (!bffBaseUrl) throw new Error('bffBaseUrl is required');
    const url = new URL(bffBaseUrl);
    if (url.protocol !== 'https:' && url.hostname !== 'localhost' && url.hostname !== '127.0.0.1') {
      throw new Error('bffBaseUrl must use HTTPS (localhost is exempt)');
    }
    this._base = bffBaseUrl.replace(/\/$/, '');
    this._refreshTimer = null;
  }

  // ── public API ─────────────────────────────────────────────────────────────

  async login(did) {
    // 1. Get challenge options from BFF
    let startResp;
    try {
      const r = await fetch(`${this._base}/start`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ did }),
      });
      if (r.status === 404) throw new DIDNotFoundError();
      if (!r.ok) throw new LoginFailedError(`/login/start failed: ${r.status}`);
      startResp = await r.json();
    } catch (e) {
      if (e instanceof DIDNotFoundError || e instanceof LoginFailedError) throw e;
      throw new LoginFailedError(e.message);
    }

    // 2. WebAuthn assertion
    let assertion;
    try {
      assertion = await startAuthentication({
        optionsJSON: {
          challenge: startResp.challenge,
          allowCredentials: startResp.allow_credentials,
          userVerification: startResp.user_verification,
          timeout: startResp.timeout,
        },
      });
    } catch (e) {
      if (e.name === 'NotAllowedError') throw new LoginCancelledError();
      throw new LoginFailedError(e.message);
    }

    // 3. Submit assertion to BFF
    let completeResp;
    try {
      const r = await fetch(`${this._base}/complete`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ did, assertion }),
      });
      if (r.status === 404) throw new DIDNotFoundError();
      if (!r.ok) {
        const body = await r.json().catch(() => ({}));
        throw new LoginFailedError(body.detail || `Login rejected: ${r.status}`);
      }
      completeResp = await r.json();
    } catch (e) {
      if (e instanceof DIDNotFoundError || e instanceof LoginFailedError) throw e;
      throw new LoginFailedError(e.message);
    }

    this._storeTokens(completeResp);
    this._scheduleRefresh(completeResp.expires_at);

    return {
      did: completeResp.did,
      sessionToken: completeResp.session_token,
      refreshToken: completeResp.refresh_token,
      expiresAt: completeResp.expires_at,
      refreshExpiresAt: completeResp.refresh_expires_at,
    };
  }

  async refresh() {
    const refreshToken = localStorage.getItem(LS_REFRESH);
    if (!refreshToken) throw new SessionExpiredError();

    let resp;
    try {
      const r = await fetch(`${this._base}/refresh`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ refresh_token: refreshToken }),
      });
      if (!r.ok) {
        this._clearTokens();
        throw new SessionExpiredError();
      }
      resp = await r.json();
    } catch (e) {
      if (e instanceof SessionExpiredError) throw e;
      this._clearTokens();
      throw new SessionExpiredError();
    }

    localStorage.setItem(LS_SESSION, resp.session_token);
    localStorage.setItem(LS_EXPIRES, String(resp.expires_at));
    this._scheduleRefresh(resp.expires_at);

    return {
      sessionToken: resp.session_token,
      did: resp.did,
      expiresAt: resp.expires_at,
    };
  }

  async logout() {
    const refreshToken = localStorage.getItem(LS_REFRESH);
    if (refreshToken) {
      await fetch(`${this._base}/logout`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ refresh_token: refreshToken }),
      }).catch(() => {});
    }
    this._clearTokens();
  }

  async getToken() {
    const token = localStorage.getItem(LS_SESSION);
    if (!token) return null;
    const exp = Number(localStorage.getItem(LS_EXPIRES));
    const nowSecs = Date.now() / 1000;
    if (exp - nowSecs < REFRESH_BEFORE_SECS) {
      try {
        await this.refresh();
      } catch {
        return null;
      }
    }
    return localStorage.getItem(LS_SESSION);
  }

  getDid() {
    return localStorage.getItem(LS_DID);
  }

  isLoggedIn() {
    const token = localStorage.getItem(LS_SESSION);
    const exp = Number(localStorage.getItem(LS_EXPIRES));
    return !!token && exp > Date.now() / 1000;
  }

  // ── private ────────────────────────────────────────────────────────────────

  _storeTokens(resp) {
    localStorage.setItem(LS_SESSION, resp.session_token);
    localStorage.setItem(LS_REFRESH, resp.refresh_token);
    localStorage.setItem(LS_DID, resp.did);
    localStorage.setItem(LS_EXPIRES, String(resp.expires_at));
  }

  _clearTokens() {
    [LS_SESSION, LS_REFRESH, LS_DID, LS_EXPIRES].forEach(k => localStorage.removeItem(k));
    if (this._refreshTimer !== null) {
      clearTimeout(this._refreshTimer);
      this._refreshTimer = null;
    }
  }

  _scheduleRefresh(expiresAt) {
    if (this._refreshTimer !== null) clearTimeout(this._refreshTimer);
    const nowSecs = Date.now() / 1000;
    const delayMs = Math.max(0, (expiresAt - nowSecs - REFRESH_BEFORE_SECS) * 1000);
    this._refreshTimer = setTimeout(async () => {
      try {
        const result = await this.refresh();
        // refresh() already re-schedules the next timer
      } catch {
        // session expired — caller must re-login
      }
    }, delayMs);
  }
}
