# BFF Login API Contract

Base path: `/login`

All requests and responses are JSON. HTTPS required in production.

---

## POST /login/start

Initiate a WebAuthn authentication ceremony. Returns the challenge options to pass to `@simplewebauthn/browser`'s `startAuthentication()`.

### Request Body

```json
{ "did": "did:local:<uuid4>" }
```

### Response 200

```json
{
  "challenge": "<base64url-encoded 32-byte random challenge>",
  "allow_credentials": [
    { "type": "public-key", "id": "<credential-id base64url>" }
  ],
  "user_verification": "preferred",
  "timeout": 60000
}
```

### Error Responses

| Status | Condition |
|--------|-----------|
| 404 | DID not found in promoted enrolments |
| 422 | Missing or malformed `did` field |

---

## POST /login/complete

Submit the WebAuthn assertion. The BFF verifies the signature and the trust bundle, then issues tokens.

### Request Body

```json
{
  "did": "did:local:<uuid4>",
  "assertion": {
    "id": "<credential-id base64url>",
    "rawId": "<rawId base64url>",
    "response": {
      "authenticatorData": "<base64url>",
      "clientDataJSON": "<base64url>",
      "signature": "<base64url>"
    },
    "type": "public-key"
  }
}
```

### Response 200

```json
{
  "session_token": "<JWT string>",
  "refresh_token": "<64-char hex string>",
  "did": "did:local:<uuid4>",
  "expires_at": 1234567890,
  "refresh_expires_at": 1234567890
}
```

### Error Responses

| Status | Condition |
|--------|-----------|
| 401 | Assertion signature verification failed |
| 401 | DID not found or not active in current trust bundle |
| 401 | Challenge expired or not found (replay / timeout) |
| 422 | Malformed assertion object |

---

## POST /login/refresh

Exchange a valid refresh token for a new session token. Re-verifies the trust bundle.

### Request Body

```json
{ "refresh_token": "<64-char hex string>" }
```

### Response 200

```json
{
  "session_token": "<JWT string>",
  "did": "did:local:<uuid4>",
  "expires_at": 1234567890
}
```

### Error Responses

| Status | Condition |
|--------|-----------|
| 401 | Refresh token not found, expired, or invalidated |
| 401 | DID revoked — no longer in trust bundle |

---

## POST /login/logout

Invalidate the refresh token. Session token expires naturally.

### Request Body

```json
{ "refresh_token": "<64-char hex string>" }
```

### Response 200

```json
{ "ok": true }
```

No error if the token is already gone (idempotent).

---

## GET /login/verify

Verify a session token and return the DID it encodes. Used by resource servers or the demo UI to confirm a token is valid.

### Request Header

```
Authorization: Bearer <session_token>
```

### Response 200

```json
{
  "did": "did:local:<uuid4>",
  "expires_at": 1234567890
}
```

### Error Responses

| Status | Condition |
|--------|-----------|
| 401 | Token missing, malformed, expired, or signature invalid |
