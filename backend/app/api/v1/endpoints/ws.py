import asyncio
import json
from collections import defaultdict

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect
from loguru import logger

from app.core.constants import GUEST_SESSION_TIMEOUT, WS_PING_INTERVAL, WS_PING_TIMEOUT
from app.core.redis import get_redis

router = APIRouter()

# WebSocket security limits
WS_MAX_MESSAGE_SIZE = 64 * 1024  # 64 KB max message size
WS_MSG_RATE_LIMIT = 60  # max messages per window
WS_MSG_RATE_WINDOW = 60  # window in seconds

# In-memory connection registry: user_id -> set of WebSocket connections
_connections: dict[str, set[WebSocket]] = defaultdict(set)
_connections_lock = asyncio.Lock()


async def _authenticate_ws(ticket: str) -> dict | None:
    """Validate a one-time WebSocket ticket from Redis."""
    redis = get_redis()
    key = f"ws:ticket:{ticket}"
    data = await redis.get(key)
    if data is None:
        return None

    # Delete immediately — one-time use
    await redis.delete(key)

    try:
        return dict(json.loads(data))
    except (json.JSONDecodeError, TypeError):
        return None


@router.websocket("/ws")
async def websocket_endpoint(ws: WebSocket, ticket: str = Query(...)) -> None:
    payload = await _authenticate_ws(ticket)
    if payload is None:
        await ws.close(code=4001, reason="Authentication failed")
        return

    user_id = payload["sub"]
    role = payload["role"]

    await ws.accept()
    async with _connections_lock:
        _connections[user_id].add(ws)
    logger.info("WebSocket connected", extra={"user_id": user_id, "role": role})

    guest_timeout_task = None
    ping_task = None
    # Use mutable container so closures share the same reference
    activity = {"last": asyncio.get_event_loop().time()}
    try:
        last_pong = asyncio.get_event_loop().time()

        # Guest inactivity timeout — resets on each received message/pong
        if role == "GUEST":

            async def _guest_timeout() -> None:
                while True:
                    elapsed = asyncio.get_event_loop().time() - activity["last"]
                    remaining = GUEST_SESSION_TIMEOUT - elapsed
                    if remaining <= 0:
                        logger.info(
                            "Guest session timeout (inactivity)", extra={"user_id": user_id}
                        )
                        await force_logout(user_id)
                        return
                    await asyncio.sleep(min(remaining, 60))

            guest_timeout_task = asyncio.create_task(_guest_timeout())

        async def ping_loop() -> None:
            while True:
                await asyncio.sleep(WS_PING_INTERVAL)
                now = asyncio.get_event_loop().time()
                if now - last_pong > WS_PING_TIMEOUT:
                    logger.warning("WebSocket ping timeout", extra={"user_id": user_id})
                    await ws.close(code=4002, reason="Ping timeout")
                    return
                try:
                    await ws.send_json({"type": "PING", "timestamp": now})
                except Exception:
                    logger.debug(
                        "WebSocket ping send failed, closing loop", extra={"user_id": user_id}
                    )
                    return

        ping_task = asyncio.create_task(ping_loop())

        msg_count = 0
        msg_window_start = asyncio.get_event_loop().time()

        while True:
            data = await ws.receive_text()

            # Message size limit
            if len(data) > WS_MAX_MESSAGE_SIZE:
                await ws.close(code=4004, reason="Message too large")
                return

            # Message rate limiting
            now = asyncio.get_event_loop().time()
            if now - msg_window_start > WS_MSG_RATE_WINDOW:
                msg_count = 0
                msg_window_start = now
            msg_count += 1
            if msg_count > WS_MSG_RATE_LIMIT:
                await ws.close(code=4005, reason="Rate limit exceeded")
                return

            msg = json.loads(data)
            activity["last"] = now

            if msg.get("type") == "PONG":
                last_pong = asyncio.get_event_loop().time()

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected", extra={"user_id": user_id})
    except Exception as e:
        logger.error("WebSocket error", extra={"user_id": user_id, "error": str(e)})
    finally:
        if ping_task:
            ping_task.cancel()
        if guest_timeout_task:
            guest_timeout_task.cancel()
        async with _connections_lock:
            _connections[user_id].discard(ws)
            if not _connections[user_id]:
                del _connections[user_id]


async def send_to_user(user_id: str, message: dict) -> None:
    """Publish a message to a user via Redis Pub/Sub (reaches all workers)."""
    try:
        redis = get_redis()
        await redis.publish(f"ws:user:{user_id}", json.dumps(message))
    except Exception:
        logger.warning("Failed to publish WS message via Redis", exc_info=True)
        # Fallback: try local delivery
        await _local_send(user_id, message)


async def force_logout(user_id: str) -> None:
    """Publish a force-logout command via Redis Pub/Sub."""
    try:
        redis = get_redis()
        await redis.publish(f"ws:logout:{user_id}", "1")
    except Exception:
        logger.warning("Failed to publish force logout via Redis", exc_info=True)
        # Fallback: local
        await _local_force_logout(user_id)


async def _local_send(user_id: str, message: dict) -> None:
    """Send a message to all local WebSocket connections for a user."""
    async with _connections_lock:
        sockets = list(_connections.get(user_id, []))
    for ws in sockets:
        try:
            await ws.send_json(message)
        except Exception:
            logger.warning(
                "Failed to send WS message to user, discarding connection",
                extra={"user_id": user_id},
                exc_info=True,
            )
            async with _connections_lock:
                _connections[user_id].discard(ws)


async def _local_force_logout(user_id: str) -> None:
    """Send FORCE_LOGOUT message and close all local connections for a user."""
    async with _connections_lock:
        sockets = list(_connections.get(user_id, []))
    for ws in sockets:
        try:
            await ws.send_json({"type": "FORCE_LOGOUT"})
            await ws.close(code=4003, reason="Session expired")
        except Exception:
            logger.warning(
                "Failed to send force logout to user", extra={"user_id": user_id}, exc_info=True
            )
    async with _connections_lock:
        _connections.pop(user_id, None)


# --- Redis Pub/Sub subscriber (started in lifespan) ---

_subscriber_task: asyncio.Task | None = None


async def start_redis_subscriber() -> None:
    """Start the Redis Pub/Sub subscriber background task."""
    global _subscriber_task
    _subscriber_task = asyncio.create_task(_subscribe_with_retry())


async def stop_redis_subscriber() -> None:
    """Stop the Redis Pub/Sub subscriber."""
    global _subscriber_task
    if _subscriber_task:
        _subscriber_task.cancel()
        try:
            await _subscriber_task
        except asyncio.CancelledError:
            pass
        _subscriber_task = None


async def _subscribe_with_retry() -> None:
    """Wrap Redis Pub/Sub subscriber with automatic reconnection."""
    backoff = 5
    max_backoff = 60
    while True:
        try:
            await _redis_subscriber()
            backoff = 5
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.error(
                "Redis Pub/Sub subscriber crashed, reconnecting in %ds",
                backoff,
                exc_info=True,
            )
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, max_backoff)


async def _redis_subscriber() -> None:
    """Subscribe to ws:user:* and ws:logout:* channels, dispatching to local connections."""
    redis = get_redis()
    pubsub = redis.pubsub()
    try:
        await pubsub.psubscribe("ws:user:*", "ws:logout:*")
        logger.info("Redis Pub/Sub subscriber started for WebSocket")

        async for msg in pubsub.listen():
            if msg["type"] != "pmessage":
                continue

            channel = msg["channel"]
            if isinstance(channel, bytes):
                channel = channel.decode()

            try:
                if channel.startswith("ws:user:"):
                    user_id = channel[len("ws:user:") :]
                    data = msg["data"]
                    if isinstance(data, bytes):
                        data = data.decode()
                    message = json.loads(data)
                    await _local_send(user_id, message)

                elif channel.startswith("ws:logout:"):
                    user_id = channel[len("ws:logout:") :]
                    await _local_force_logout(user_id)
            except Exception:
                logger.warning("Error processing Pub/Sub message", exc_info=True)

    except asyncio.CancelledError:
        logger.info("Redis Pub/Sub subscriber stopped")
        raise
    except Exception:
        logger.error("Redis Pub/Sub subscriber crashed", exc_info=True)
        raise
    finally:
        try:
            await pubsub.unsubscribe()
            await pubsub.close()
        except Exception:
            logger.debug("Error during pubsub cleanup", exc_info=True)
