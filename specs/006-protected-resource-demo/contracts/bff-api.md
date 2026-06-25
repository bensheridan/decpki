# BFF Protected Resource API Contract

Base path: `/api`

All responses are JSON. HTTPS required in production.

---

## GET /api/me

Return identity information for the currently authenticated user.

### Request Header

```
Authorization: Bearer <session_token>
```

### Response 200

```json
{
  "did": "did:local:<uuid4>",
  "issued_at": 1234567890,
  "expires_at": 1234568790,
  "message": "Hello, did:local:<uuid4>"
}
```

| Field | Type | Description |
|-------|------|-------------|
| `did` | string | The authenticated user's W3C DID |
| `issued_at` | int (Unix timestamp) | When the session token was issued |
| `expires_at` | int (Unix timestamp) | When the session token expires |
| `message` | string | Human-readable greeting for the demo UI |

### Error Responses

| Status | Condition |
|--------|-----------|
| 401 | `Authorization` header missing or not in `Bearer <token>` format |
| 401 | Token is malformed, tampered, or signed with the wrong key |
| 401 | Token has expired |
