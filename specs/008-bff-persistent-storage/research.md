# Research: BFF Persistent Storage

## Storage Backend

**Decision**: SQLite via Python's `sqlite3` stdlib module.

**Rationale**: Zero new dependencies; ships with every Python installation. File-based so the
path is trivially configurable via an environment variable. WAL mode gives safe concurrent writes
within a single process. A single `.db` file is easy to delete, back up, or inspect. Handles
TTL pruning with `DELETE WHERE expires_at < ?` natively.

**Alternatives considered**:
- JSON files — simpler to inspect but require manual file locking and are not atomic on writes,
  making crash safety harder to guarantee (FR-004).
- Redis / PostgreSQL — add a required external service, breaking the "single process demo" goal.
- TinyDB / shelve — third-party or awkward APIs without meaningful advantage over sqlite3.

---

## Schema Design

Three tables map 1-to-1 to the existing in-memory structures in `SessionStore`:

| Table | Key | Data columns |
|---|---|---|
| `challenges` | `challenge_hex TEXT PK` | `did`, `credential_id`, `public_key_hex`, `algorithm`, `issued_at`, `expires_at` |
| `refresh_tokens` | `token_hex TEXT PK` | `did`, `issued_at`, `expires_at`, `last_jti` |
| `jti_blocklist` | `jti TEXT PK` | `added_at`, `original_exp` |

The `sessions_by_did` in-memory secondary index is NOT persisted as a separate table — it is
derived from `refresh_tokens` by `did` column with an index on `did`. This avoids sync bugs.

---

## Interface Preservation

The existing `SessionStore` public API in `bff/session.py` will be kept identical:
`create_challenge`, `consume_challenge`, `issue_refresh_token`, `consume_refresh_token`,
`revoke_refresh_token`, `issue_session_token`, `verify_session_token`, `is_jti_revoked`,
`list_sessions`, `revoke_session`.

The SQLite-backed implementation will be a drop-in replacement — `main.py` requires no changes
beyond `_session_store = SqliteSessionStore(path=...)` at startup.

---

## Startup Pruning

On startup, expired rows are pruned:
- `DELETE FROM challenges WHERE expires_at < now`
- `DELETE FROM refresh_tokens WHERE expires_at < now`
- `DELETE FROM jti_blocklist WHERE original_exp < now`

This prevents unbounded growth and means the blocklist is only retained as long as the corresponding
JWT could still be valid (FR-005).

---

## Crash Safety

SQLite WAL mode (`PRAGMA journal_mode=WAL`) is enabled on connection open. Each write is a
committed transaction. A process killed mid-write leaves the WAL file in a recoverable state —
SQLite rolls back incomplete transactions automatically on the next open.

---

## Test Strategy

- Unit tests use `SqliteSessionStore(path=":memory:")` (SQLite in-memory mode) — same code path,
  no disk I/O, fully isolated per test.
- One integration test writes to a temp file, restarts a fresh `SqliteSessionStore` instance
  against it, and asserts state is recovered.
- Existing `bff/tests/test_sessions.py` is updated to use the new class.

---

## Configuration

| Env var | Default | Meaning |
|---|---|---|
| `BFF_STORE_PATH` | `/tmp/decpki-bff.db` | Path to SQLite file; `:memory:` disables persistence |

---

## Constitution Gate

This feature affects only the BFF session layer, not the PKI trust path. The Merkle-proof identity
verification, ed25519 validator signatures, and offline bundle verification are unchanged. No
constitution gates are violated.
