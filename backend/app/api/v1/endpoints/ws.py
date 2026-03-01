import asyncio
import json
from collections import defaultdict

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect
from loguru import logger

from app.core.constants import GUEST_SESSION_TIMEOUT, WS_PING_INTERVAL, WS_PING_TIMEOUT
from app.core.redis import get_redis

router = APIRouter()

# In-memory connection registry: user_id -> set of WebSocket connections
_connections: dict[str, set[WebSocket]] = defaultdict(set)


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
        return json.loads(data)
    except (json.JSONDecodeError, TypeError):
        return None


@router.websocket("/ws")
async def websocket_endpoint(ws: WebSocket, ticket: str = Query(...)):
    payload = await _authenticate_ws(ticket)
    if payload is None:
        await ws.close(code=4001, reason="Authentication failed")
        return

    user_id = payload["sub"]
    role = payload["role"]

    await ws.accept()
    _connections[user_id].add(ws)
    logger.info("WebSocket connected", extra={"user_id": user_id, "role": role})

    guest_timeout_task = None
    try:
        last_pong = asyncio.get_event_loop().time()

        # Schedule guest force-logout after 45 minutes
        if role == "GUEST":
            async def _guest_timeout():
                await asyncio.sleep(GUEST_SESSION_TIMEOUT)
                logger.info("Guest session timeout", extra={"user_id": user_id})
                await force_logout(user_id)

            guest_timeout_task = asyncio.create_task(_guest_timeout())

        async def ping_loop():
            nonlocal last_pong
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
                    return

        ping_task = asyncio.create_task(ping_loop())

        while True:
            data = await ws.receive_text()
            msg = json.loads(data)

            if msg.get("type") == "PONG":
                last_pong = asyncio.get_event_loop().time()

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected", extra={"user_id": user_id})
    except Exception as e:
        logger.error("WebSocket error", extra={"user_id": user_id, "error": str(e)})
    finally:
        ping_task.cancel()
        if guest_timeout_task:
            guest_timeout_task.cancel()
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
    for ws in list(_connections.get(user_id, [])):
        try:
            await ws.send_json(message)
        except Exception:
            _connections[user_id].discard(ws)


async def _local_force_logout(user_id: str) -> None:
    """Send FORCE_LOGOUT message and close all local connections for a user."""
    for ws in list(_connections.get(user_id, [])):
        try:
            await ws.send_json({"type": "FORCE_LOGOUT"})
            await ws.close(code=4003, reason="Session expired")
        except Exception:
            pass
    _connections.pop(user_id, None)


# --- Redis Pub/Sub subscriber (started in lifespan) ---

_subscriber_task: asyncio.Task | None = None


async def start_redis_subscriber() -> None:
    """Start the Redis Pub/Sub subscriber background task."""
    global _subscriber_task
    _subscriber_task = asyncio.create_task(_redis_subscriber())


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


async def _redis_subscriber() -> None:
    """Subscribe to ws:user:* and ws:logout:* channels, dispatching to local connections."""
    try:
        redis = get_redis()
        pubsub = redis.pubsub()
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
                    user_id = channel[len("ws:user:"):]
                    data = msg["data"]
                    if isinstance(data, bytes):
                        data = data.decode()
                    message = json.loads(data)
                    await _local_send(user_id, message)

                elif channel.startswith("ws:logout:"):
                    user_id = channel[len("ws:logout:"):]
                    await _local_force_logout(user_id)
            except Exception:
                logger.warning("Error processing Pub/Sub message", exc_info=True)

    except asyncio.CancelledError:
        logger.info("Redis Pub/Sub subscriber stopped")
        raise
    except Exception:
        logger.error("Redis Pub/Sub subscriber crashed", exc_info=True)
