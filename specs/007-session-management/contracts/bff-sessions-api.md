# BFF Sessions API Contract

Base path: `/api`

All requests and responses are JSON. HTTPS required in production.

The caller must always provide a valid `Authorization: Bearer <session_token>` header. All endpoints return 401 if the token is missing, expired, or revoked.

---

## GET /api/sessions

List all active sessions for the authenticated DID.

### Request Headers

```
Authorization: Bearer <session_token>
```

### Request Body

```json
{ "refresh_token": "<64-char hex string>" }
```

The caller's refresh token is used to mark the current session with `is_current: true`. It is never returned in the response.

### Response 200

```json
{
  "sessions": [
    {
      "session_id": "<16 hex chars>",
      "did": "did:local:<uuid4>",
      "issued_at": 1234567890,
      "expires_at": 1234567890,
      "is_current": true
    },
    {
      "session_id": "<16 hex chars>",
      "did": "did:local:<uuid4>",
      "issued_at": 1234567890,
      "expires_at": 1234567890,
      "is_current": false
    }
  ]
}
```

### Error Responses

| Status | Condition |
|--------|-----------|
| 401 | Bearer token missing, expired, or revoked |
| 422 | Missing `refresh_token` in body |

---

## DELETE /api/sessions/{session_id}

Revoke a specific session by its ID. The session token and refresh token for that session are immediately invalidated.

### Path Parameter

| Parameter | Type | Description |
|-----------|------|-------------|
| `session_id` | `string (16 hex chars)` | The session ID from the session list. |

### Request Headers

```
Authorization: Bearer <session_token>
```

### Response 200

```json
{ "ok": true, "self_revoked": false }
```

`self_revoked: true` when the caller revoked their own current session — the client should log out immediately.

### Error Responses

| Status | Condition |
|--------|-----------|
| 401 | Bearer token missing, expired, or revoked |
| 404 | Session ID not found (already revoked or expired) |
