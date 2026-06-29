# Contract: Quickstart Script Interfaces

These are CLI tool contracts — the scripts are the interface. Each script must honour the
argument schema, exit codes, and stdout conventions documented here.

---

## `scripts/start-demo.sh`

### Usage

```
scripts/start-demo.sh [--bff-port PORT] [--demo-port PORT]
```

### Flags

| Flag | Default | Description |
|---|---|---|
| `--bff-port PORT` | `$BFF_PORT` or `8000` | Port for the FastAPI BFF |
| `--demo-port PORT` | `$DEMO_PORT` or `3000` | Port for the browser demo server |

### Environment Variables

| Variable | Effect |
|---|---|
| `SESSION_SECRET` | If set, used as the BFF signing key. If unset, auto-generated with a warning. |
| `BFF_STORE_PATH` | SQLite path for the BFF session store (default `/tmp/decpki-bff.db`). |
| `BUNDLE_PATH` | Trust bundle path passed to the browser demo server (default `/tmp/bundle.cbor`). |

### Stdout Contract

On successful start the script MUST print:

```
[decpki] BFF listening at http://localhost:8000
[decpki] Demo server listening at http://localhost:3000
[decpki] Press Ctrl-C to stop.
```

On port conflict:
```
ERROR: port 8000 is already in use. Stop the existing process or set BFF_PORT=<other>.
```

### Exit Codes

| Code | Meaning |
|---|---|
| 0 | Clean shutdown (Ctrl-C or SIGTERM) |
| 1 | Startup failure (port conflict, missing dependency, etc.) |

---

## `scripts/setup-validators.sh`

### Usage

```
scripts/setup-validators.sh
```

No positional arguments. All configuration via environment variables.

### Environment Variables

| Variable | Default | Description |
|---|---|---|
| `KEY_DIR` | `/tmp` | Directory where key files are written |
| `BUNDLE_PATH` | `/tmp/bundle.cbor` | Where to write the initial trust bundle |

### Stdout Contract

```
[decpki] Generating alpha validator keypair → /tmp/alpha.key.json
[decpki] Generating beta validator keypair  → /tmp/beta.key.json
[decpki] Generating gamma validator keypair → /tmp/gamma.key.json
[decpki] Generating trust bundle            → /tmp/bundle.cbor
[decpki] Setup complete. Run: scripts/start-demo.sh
```

If a key file already exists:
```
[decpki] /tmp/alpha.key.json already exists — skipping.
```

### Exit Codes

| Code | Meaning |
|---|---|
| 0 | Success (all keys + bundle ready) |
| 1 | Failure (missing `decpki` CLI, write error, etc.) |

---

## `scripts/promote-enrolment.sh`

### Usage

```
scripts/promote-enrolment.sh <request-id>
```

`<request-id>` is the UUID from the registration output (e.g. `e61cfdc7-4ac1-4b24-bd4d-79892438618e`).

### Environment Variables

| Variable | Default | Description |
|---|---|---|
| `KEY_DIR` | `/tmp` | Directory containing `alpha.key.json` and `beta.key.json` |
| `ENROLMENT_DIR` | `/tmp/decpki-enrolments` | Directory containing pending enrolment JSON files |
| `BUNDLE_PATH` | `/tmp/bundle.cbor` | Where to write the regenerated trust bundle |

### Stdout Contract

```
[decpki] Signing with alpha validator...
[decpki] Signing with beta validator...
[decpki] Promoting enrolment e61cfdc7...
[decpki] Regenerating trust bundle → /tmp/bundle.cbor
[decpki] Done. DID is now active. Log in at http://localhost:3000/login.html
```

### Exit Codes

| Code | Meaning |
|---|---|
| 0 | Success |
| 1 | Request file not found, already promoted, or signing failure |
