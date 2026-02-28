import asyncio
import json
from collections import defaultdict

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect
from loguru import logger

from app.core.security import decode_access_token
from app.services.auth import validate_session

router = APIRouter()

# In-memory connection registry: user_id -> set of WebSocket connections
_connections: dict[str, set[WebSocket]] = defaultdict(set)

PING_INTERVAL = 30  # seconds
PING_TIMEOUT = 90  # seconds
GUEST_SESSION_TIMEOUT = 45 * 60  # 45 minutes in seconds


async def _authenticate_ws(token: str) -> dict | None:
    """Validate JWT + Redis session for WebSocket."""
    payload = decode_access_token(token)
    if payload is None:
        return None

    user_id = payload.get("sub")
    role = payload.get("role")
    jti = payload.get("jti")

    if not all([user_id, role, jti]):
        return None

    is_valid = await validate_session(user_id, role, jti)
    if not is_valid:
        return None

    return payload


@router.websocket("/ws")
async def websocket_endpoint(ws: WebSocket, token: str = Query(...)):
    payload = await _authenticate_ws(token)
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
                await asyncio.sleep(PING_INTERVAL)
                now = asyncio.get_event_loop().time()
                if now - last_pong > PING_TIMEOUT:
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
    """Send a message to all WebSocket connections for a user."""
    for ws in list(_connections.get(user_id, [])):
        try:
            await ws.send_json(message)
        except Exception:
            _connections[user_id].discard(ws)


async def force_logout(user_id: str) -> None:
    """Send FORCE_LOGOUT message and close all connections for a user."""
    for ws in list(_connections.get(user_id, [])):
        try:
            await ws.send_json({"type": "FORCE_LOGOUT"})
            await ws.close(code=4003, reason="Session expired")
        except Exception:
            pass
    _connections.pop(user_id, None)
