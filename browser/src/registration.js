export class RegistrationCancelledError extends Error {
  constructor() { super('Registration cancelled by user'); this.name = 'RegistrationCancelledError'; }
}

export class AlgorithmNotSupportedError extends Error {
  constructor() { super('Device does not support ed25519 or ES256 credentials'); this.name = 'AlgorithmNotSupportedError'; }
}

export class OwnershipProofFailedError extends Error {
  constructor() { super('Ownership proof for existing DID failed'); this.name = 'OwnershipProofFailedError'; }
}

export class RegistrationError extends Error {
  constructor(message) { super(message); this.name = 'RegistrationError'; }
}

export class DecPKIRegistration {
  constructor(config) {
    if (!config || !config.bffBaseUrl) {
      throw new Error('DecPKIRegistration requires config.bffBaseUrl');
    }
    const url = config.bffBaseUrl;
    if (!url.startsWith('https://') && !url.startsWith('http://localhost') && !url.startsWith('http://127.0.0.1')) {
      throw new Error('bffBaseUrl must use HTTPS (http:// is only permitted for localhost)');
    }
    this._bffBaseUrl = url.replace(/\/$/, '');
  }

  async register() {
    return this._doRegister(null);
  }

  async addCredential(existingDid) {
    return this._doRegister(existingDid);
  }

  async _doRegister(existingDid) {
    const { startRegistration, startAuthentication } = await import('@simplewebauthn/browser');

    const startUrl = existingDid
      ? `${this._bffBaseUrl}/start?did=${encodeURIComponent(existingDid)}`
      : `${this._bffBaseUrl}/start`;

    const startResp = await fetch(startUrl, { method: 'POST' });
    if (!startResp.ok) {
      const body = await startResp.json().catch(() => ({}));
      throw new RegistrationError(body.detail || `Start failed: ${startResp.status}`);
    }
    const startData = await startResp.json();

    let ownershipAssertion = null;
    if (startData.request_type === 'add_credential' && startData.ownership_nonce) {
      try {
        ownershipAssertion = await startAuthentication({
          challenge: startData.ownership_nonce,
          allowCredentials: [],
          userVerification: 'preferred',
        });
      } catch (e) {
        if (e.name === 'NotAllowedError') throw new RegistrationCancelledError();
        throw new OwnershipProofFailedError();
      }
    }

    let credential;
    try {
      credential = await startRegistration({
        challenge: startData.challenge,
        rp: startData.rp,
        user: startData.user,
        pubKeyCredParams: startData.pubKeyCredParams,
        timeout: startData.timeout,
        attestation: startData.attestation,
      });
    } catch (e) {
      if (e.name === 'NotAllowedError') throw new RegistrationCancelledError();
      throw new RegistrationError(e.message);
    }

    const submitResp = await fetch(`${this._bffBaseUrl}/submit`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        pending_did: startData.pending_did,
        credential,
        ownership_assertion: ownershipAssertion,
      }),
    });

    if (!submitResp.ok) {
      const body = await submitResp.json().catch(() => ({}));
      if (submitResp.status === 422) {
        const detail = body.detail || '';
        if (detail.includes('Unsupported COSE algorithm')) {
          throw new AlgorithmNotSupportedError();
        }
        if (detail.includes('Ownership proof')) {
          throw new OwnershipProofFailedError();
        }
      }
      throw new RegistrationError(body.detail || `Submit failed: ${submitResp.status}`);
    }

    const result = await submitResp.json();
    return {
      requestId: result.request_id,
      did: result.did,
      status: result.status,
      threshold: result.threshold,
      signaturesCollected: result.signatures_collected,
      expiresAt: result.expires_at,
    };
  }

  async getStatus(requestId) {
    const resp = await fetch(`${this._bffBaseUrl}/${requestId}`);
    if (resp.status === 404) throw new RegistrationError(`Request ${requestId} not found`);
    if (!resp.ok) throw new RegistrationError(`Status check failed: ${resp.status}`);
    const data = await resp.json();
    return {
      requestId: data.request_id,
      did: data.did,
      status: data.status,
      signaturesCollected: data.signatures_collected,
      threshold: data.threshold,
      expiresAt: data.expires_at,
    };
  }
}
