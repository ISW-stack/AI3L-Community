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
| `NOTIFICATION` | New activity | A comment, reaction, or mention on content the user is subscribed to |
| `FORCE_LOGOUT` | Admin action | Server-initiated session termination (e.g., account banned). Client must clear local session state and redirect to login. |

### `NOTIFICATION` payload

```json
{
  "type": "NOTIFICATION",
  "id": "uuid",
  "kind": "comment",
  "post_id": "uuid",
  "actor_display_name": "Jane",
  "created_at": "2026-01-01T00:00:00Z"
}
```

### `FORCE_LOGOUT` payload

```json
{
  "type": "FORCE_LOGOUT",
  "reason": "account_banned"
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
