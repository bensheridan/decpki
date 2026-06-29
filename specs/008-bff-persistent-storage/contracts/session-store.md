# Contract: SessionStore Interface

This contract defines the interface that `SqliteSessionStore` must fulfil. It is identical to
the existing in-memory `SessionStore` in `bff/session.py`. All callers in `bff/main.py` depend
on this contract without change.

## Methods

### `create_challenge(did, credential_id, public_key_hex, algorithm) → challenge_hex`

- Generates 32 random bytes, stores the challenge record, returns the hex string.
- TTL: `now + 60` seconds.
- Must be idempotent per distinct `challenge_hex` (no collision expected given 256-bit entropy).

### `consume_challenge(challenge_hex) → dict | None`

- Atomically removes and returns the record if present **and** not expired.
- Returns `None` if absent or expired.
- After return, the `challenge_hex` MUST NOT be accepted again (one-time use).

### `issue_refresh_token(did) → (token_hex, expires_at)`

- Generates 32 random bytes for the token.
- Stores with `last_jti = ""`, TTL = `REFRESH_LIFETIME_SECONDS`.
- Adds `token_hex` to the DID-indexed secondary index.

### `consume_refresh_token(token_hex) → dict | None`

- Returns the entry without deleting (token stays live across refresh cycles).
- Returns `None` if absent or expired.

### `revoke_refresh_token(token_hex)`

- Removes the record and removes `token_hex` from the DID index.

### `issue_session_token(did, refresh_token_hex=None) → (jwt_str, expires_at)`

- Mints a HS256 JWT with `sub=did`, `jti=uuid4`, `exp=now+SESSION_LIFETIME_SECONDS`.
- If `refresh_token_hex` is provided and exists, updates `last_jti` in the record.

### `verify_session_token(token) → payload_dict`

- Decodes and validates the JWT; raises `JWTError` on failure.

### `is_jti_revoked(jti) → bool`

- Returns `True` if `jti` is in the blocklist **and** `original_exp > now`.
- A pruned or absent entry returns `False`.

### `list_sessions(did) → list[dict]`

Each dict contains: `session_id` (first 16 chars of `token_hex`), `did`, `issued_at`,
`expires_at`, `last_jti`. Expired tokens are silently skipped.

### `revoke_session(session_id) → (found: bool, token_hex: str | None)`

- Finds refresh token by 16-char prefix.
- Adds `last_jti` to blocklist (if non-empty), then revokes the refresh token.
- Returns `(True, token_hex)` on success, `(False, None)` if not found.
