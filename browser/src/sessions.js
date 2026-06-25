/**
 * DecPKISessions — list, revoke, and add devices to active sessions.
 */
import { DecPKIRegistration, RegistrationCancelledError, RegistrationError } from './registration.js';

export class SessionsAuthError extends Error {
  constructor(msg = 'Session token is invalid or expired') { super(msg); this.name = 'SessionsAuthError'; }
}
export class SessionNotFoundError extends Error {
  constructor(msg = 'Session not found or already revoked') { super(msg); this.name = 'SessionNotFoundError'; }
}
export class AddDeviceCancelledError extends Error {
  constructor(msg = 'Add new device cancelled') { super(msg); this.name = 'AddDeviceCancelledError'; }
}
export class AddDeviceError extends Error {
  constructor(msg = 'Add new device failed') { super(msg); this.name = 'AddDeviceError'; }
}

export class DecPKISessions {
  /**
   * @param {{ bffBaseUrl: string, session: import('./session.js').DecPKISession }} opts
   *   bffBaseUrl: root BFF URL, e.g. 'http://localhost:8000'
   *   session: a DecPKISession instance providing getToken() and getDid()
   */
  constructor({ bffBaseUrl, session }) {
    if (!bffBaseUrl) throw new Error('bffBaseUrl is required');
    if (!session) throw new Error('session is required');
    const url = new URL(bffBaseUrl);
    if (url.protocol !== 'https:' && url.hostname !== 'localhost' && url.hostname !== '127.0.0.1') {
      throw new Error('bffBaseUrl must use HTTPS (localhost is exempt)');
    }
    this._base = bffBaseUrl.replace(/\/$/, '');
    this._session = session;
  }

  async list() {
    const token = await this._session.getToken();
    if (!token) throw new SessionsAuthError();
    const refreshToken = localStorage.getItem('decpki_refresh') || '';
    const r = await fetch(`${this._base}/api/sessions`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`,
      },
      body: JSON.stringify({ refresh_token: refreshToken }),
    });
    if (r.status === 401) throw new SessionsAuthError();
    if (!r.ok) throw new SessionsAuthError(`Unexpected error: ${r.status}`);
    const data = await r.json();
    return {
      sessions: data.sessions.map(s => ({
        sessionId: s.session_id,
        did: s.did,
        issuedAt: s.issued_at,
        expiresAt: s.expires_at,
        isCurrent: s.is_current,
      })),
    };
  }

  async revoke(sessionId) {
    const token = await this._session.getToken();
    if (!token) throw new SessionsAuthError();
    const r = await fetch(`${this._base}/api/sessions/${encodeURIComponent(sessionId)}`, {
      method: 'DELETE',
      headers: { 'Authorization': `Bearer ${token}` },
    });
    if (r.status === 401) throw new SessionsAuthError();
    if (r.status === 404) throw new SessionNotFoundError();
    if (!r.ok) throw new SessionsAuthError(`Unexpected error: ${r.status}`);
    const data = await r.json();
    return { ok: data.ok, selfRevoked: data.self_revoked };
  }

  async addDevice() {
    const did = this._session.getDid();
    if (!did) throw new AddDeviceError('No logged-in DID');
    const enrolmentBase = `${this._base}/enrolment`;
    const reg = new DecPKIRegistration({ bffBaseUrl: enrolmentBase });
    try {
      return await reg.addCredential(did);
    } catch (e) {
      if (e instanceof RegistrationCancelledError) throw new AddDeviceCancelledError();
      throw new AddDeviceError(e.message);
    }
  }
}
