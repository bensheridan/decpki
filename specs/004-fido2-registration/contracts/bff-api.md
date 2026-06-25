# BFF API Contract: FIDO2 Enrolment

Base path: `/enrolment`

All requests and responses are JSON. All endpoints require HTTPS in production.

---

## POST /enrolment/start

Begin the WebAuthn credential creation ceremony. Returns the challenge options to pass to `@simplewebauthn/browser`'s `startRegistration()`.

### Request

No body. Optional query parameter:

| Parameter | Type | Description |
|-----------|------|-------------|
| `did` | `string` (optional) | If provided, this is an `add_credential` flow for an existing DID. Triggers a nonce for ownership proof. |

### Response 200

```json
{
  "challenge": "<base64url-encoded 32-byte random challenge>",
  "rp": {
    "name": "DecPKI Prototype",
    "id": "<relying-party-id, e.g. localhost>"
  },
  "user": {
    "id": "<base64url-encoded UUID4 assigned as the new DID>",
    "name": "<placeholder, e.g. 'user'>",
    "displayName": "<placeholder>"
  },
  "pubKeyCredParams": [
    { "type": "public-key", "alg": -8 }
  ],
  "timeout": 60000,
  "attestation": "none",
  "request_type": "new",
  "pending_did": "did:local:<uuid4>"
}
```

For `add_credential` flow, `request_type` is `"add_credential"` and an additional `ownership_nonce` field is included (used by the client to prove ownership of the existing DID before submission).

### Error Responses

| Status | Condition |
|--------|-----------|
| 404 | `did` parameter provided but DID not found in ledger |

---

## POST /enrolment/submit

Submit the credential returned by `startRegistration()`. The BFF extracts the COSE public key, creates an `EnrolmentRequest`, and returns the request ID.

### Request Body

```json
{
  "pending_did": "did:local:<uuid4>",
  "credential": {
    "id": "<credential-id base64url>",
    "rawId": "<rawId base64url>",
    "response": {
      "clientDataJSON": "<base64url>",
      "attestationObject": "<base64url>"
    },
    "type": "public-key"
  },
  "ownership_assertion": null
}
```

For `add_credential` flow, `ownership_assertion` is a WebAuthn assertion object (from `startAuthentication()`) proving control of the existing DID's credential.

### Response 201

```json
{
  "request_id": "<uuid4>",
  "did": "did:local:<uuid4>",
  "status": "pending",
  "signatures_collected": 0,
  "threshold": 2,
  "expires_at": 1234567890
}
```

### Error Responses

| Status | Condition |
|--------|-----------|
| 422 | COSE algorithm is not -8 (ed25519). Message: `"Only ed25519 credentials (COSE alg -8) are accepted."` |
| 422 | Invalid `clientDataJSON` (wrong origin, wrong challenge, wrong type). |
| 422 | `ownership_assertion` missing or invalid for `add_credential` flow. |
| 409 | Credential ID already registered. |

---

## GET /enrolment/{request_id}

Check the status of an enrolment request.

### Response 200

```json
{
  "request_id": "<uuid4>",
  "did": "did:local:<uuid4>",
  "status": "pending",
  "signatures_collected": 1,
  "threshold": 2,
  "expires_at": 1234567890
}
```

`status` is one of: `"pending"`, `"promoted"`, `"expired"`, `"cancelled"`.

### Error Responses

| Status | Condition |
|--------|-----------|
| 404 | Request ID not found |

---

## GET /enrolment/

List all enrolment requests (for admin/validator use). Returns a summary array.

### Response 200

```json
[
  {
    "request_id": "<uuid4>",
    "did": "did:local:<uuid4>",
    "status": "pending",
    "signatures_collected": 1,
    "threshold": 2,
    "submitted_at": 1234567890,
    "expires_at": 1234567890
  }
]
```
