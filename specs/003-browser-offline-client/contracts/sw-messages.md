# Contract: Service Worker Message Protocol

## Overview

The Service Worker (`decpki-sw.js`) communicates with main-thread clients via `postMessage`
and the `decpki` BroadcastChannel. This contract defines all messages in both directions.

---

## Main Thread → Service Worker (postMessage to SW)

### `SYNC_REQUEST`

Ask the SW to attempt a bundle refresh immediately.

```json
{ "type": "SYNC_REQUEST" }
```

The SW replies with `SYNC_ACK` immediately. The actual sync runs async; result is broadcast
on the `decpki` channel.

### `GET_BUNDLE_STATUS`

Ask the SW for the current bundle status (expiry, sync state).

```json
{ "type": "GET_BUNDLE_STATUS" }
```

Reply (sent back to requesting client via `event.source.postMessage`):

```json
{
  "type": "BUNDLE_STATUS",
  "expiresAt": 1750000000,
  "isExpired": false,
  "syncStatus": "idle",
  "lastSync": 1749990000
}
```

---

## Service Worker → Main Thread Broadcasts (BroadcastChannel `"decpki"`)

### `BUNDLE_UPDATED`

A fresh, validated bundle has been stored in IndexedDB.

```json
{
  "type": "BUNDLE_UPDATED",
  "expiresAt": 1750000000
}
```

### `SYNC_FAILED`

The sync attempt failed. The existing bundle (if any) is unchanged.

```json
{
  "type": "SYNC_FAILED",
  "error": "HTTP 503: Service Unavailable"
}
```

### `SYNC_ACK`

Acknowledgement of a `SYNC_REQUEST`. Sent as direct reply to the requesting client.

```json
{ "type": "SYNC_ACK" }
```

---

## Invariants

- If `syncInProgress === true` in the SW and a new `SYNC_REQUEST` arrives, the SW sends
  `SYNC_ACK` immediately and does NOT start a second sync. The first sync's broadcast
  (`BUNDLE_UPDATED` or `SYNC_FAILED`) serves all waiters.
- The SW NEVER broadcasts `BUNDLE_UPDATED` for a bundle that failed validation.
- All broadcast messages include a `type` string field.
