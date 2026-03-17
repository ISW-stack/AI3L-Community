# WebSocket Protocol — AI3L Community Platform

---

## Overview

The WebSocket endpoint provides real-time push notifications to connected clients. It uses **ticket-based authentication** to avoid transmitting session cookies over the WebSocket upgrade request.

Endpoint: `ws://host/api/v1/ws?ticket=<one-time-ticket>`

---

## Authentication Flow

1. While authenticated (cookie is sent automatically), the client calls:
   ```
   POST /api/v1/auth/ws-ticket
   ```
2. The server generates a one-time ticket, stores it in Redis with a **30-second TTL**, and returns it in the response body.
3. The client opens a WebSocket connection with the ticket in the query string:
   ```
   ws://host/api/v1/ws?ticket=<one-time-ticket>
   ```
4. The server validates the ticket on connection and **immediately deletes it from Redis** (single-use).
5. Expired or already-used tickets are rejected. Unauthenticated connections are closed immediately.

---

## Heartbeat Protocol

The server sends a `PING` frame every 30 seconds to detect stale connections:

```json
{"type": "PING", "timestamp": "2026-01-01T00:00:00Z"}
```

The client must respond with:

```json
{"type": "PONG"}
```

Connections that do not respond within **90 seconds** are closed by the server.

---

## Server-Sent Message Types

| Type | Trigger | Description |
|---|---|---|
| `PING` | Every 30 seconds | Keepalive ping — client must respond with `PONG` |
| `NEW_NOTIFICATION` | New activity | A comment, reaction, or mention on content the user is subscribed to |
| `FORCE_LOGOUT` | Admin action | Server-initiated session termination (e.g., account banned). Client must clear local session state and redirect to login. |
| `NEW_DM` | Incoming DM | A new direct message was sent to the current user |
| `DM_EDITED` | DM edited | A DM the current user received was edited by the sender |
| `DM_RECALLED` | DM recalled | A DM was recalled by the sender (both parties are notified) |
| `DM_READ` | DM read | The recipient read messages in a conversation |

### `NEW_NOTIFICATION` payload

```json
{
  "type": "NEW_NOTIFICATION",
  "notification": {
    "id": "uuid",
    "kind": "comment",
    "post_id": "uuid",
    "actor_display_name": "Jane",
    "message": "Jane commented on your post.",
    "created_at": "2026-01-01T00:00:00Z"
  }
}
```

### `FORCE_LOGOUT` payload

```json
{
  "type": "FORCE_LOGOUT",
  "reason": "account_banned"
}
```

### `NEW_DM` payload

```json
{
  "type": "NEW_DM",
  "message": {
    "id": "uuid",
    "conversation_id": "uuid",
    "sender": {
      "id": "uuid",
      "display_name": "Jane",
      "avatar_url": "https://..."
    },
    "content": "Hello!",
    "attachment_url": null,
    "attachment_filename": null,
    "attachment_expires_at": null,
    "is_recalled": false,
    "is_edited": false,
    "read_at": null,
    "created_at": "2026-01-01T00:00:00Z"
  }
}
```

### `DM_EDITED` payload

```json
{
  "type": "DM_EDITED",
  "message": {
    "id": "uuid",
    "conversation_id": "uuid",
    "content": "Edited content",
    "is_edited": true,
    "created_at": "2026-01-01T00:00:00Z"
  }
}
```

### `DM_RECALLED` payload

```json
{
  "type": "DM_RECALLED",
  "message_id": "uuid",
  "conversation_id": "uuid"
}
```

### `DM_READ` payload

```json
{
  "type": "DM_READ",
  "conversation_id": "uuid",
  "read_at": "2026-01-01T00:00:00Z"
}
```

---

## Multi-Worker Fan-out

Real-time messages are delivered via **Redis Pub/Sub**. When the backend publishes a notification for a user, all Uvicorn workers receive the message and forward it to any WebSocket connections belonging to that user — regardless of which worker the connection is held by.

---

## Connection Limits

| Limit | Value |
|---|---|
| Messages per minute per connection | 60 |
| Maximum message size | 64 KB |
| Idle timeout (no PONG) | 90 seconds |
