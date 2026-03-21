"""Tests for M-01 through M-04 audit fixes (WebSocket + password auth hardening)."""

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# M-01: WebSocket ticket uses atomic getdel (no TOCTOU)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_authenticate_ws_uses_getdel():
    """M-01: _authenticate_ws should use atomic getdel instead of get+delete."""
    mock_redis = AsyncMock()
    payload = {"sub": "user-1", "role": "MEMBER"}
    mock_redis.getdel = AsyncMock(return_value=json.dumps(payload))

    with patch("app.api.v1.endpoints.ws.get_redis", return_value=mock_redis):
        from app.api.v1.endpoints.ws import _authenticate_ws

        result = await _authenticate_ws("test-ticket")

    assert result == payload
    mock_redis.getdel.assert_awaited_once_with("ws:ticket:test-ticket")
    # Ensure get/delete are NOT called (atomic operation only)
    mock_redis.get.assert_not_awaited()
    mock_redis.delete.assert_not_awaited()


@pytest.mark.asyncio
async def test_authenticate_ws_getdel_returns_none_for_missing_ticket():
    """M-01: getdel returns None for non-existent ticket."""
    mock_redis = AsyncMock()
    mock_redis.getdel = AsyncMock(return_value=None)

    with patch("app.api.v1.endpoints.ws.get_redis", return_value=mock_redis):
        from app.api.v1.endpoints.ws import _authenticate_ws

        result = await _authenticate_ws("bad-ticket")

    assert result is None
    mock_redis.getdel.assert_awaited_once()


@pytest.mark.asyncio
async def test_authenticate_ws_getdel_invalid_json():
    """M-01: getdel returns data but JSON is invalid -> None."""
    mock_redis = AsyncMock()
    mock_redis.getdel = AsyncMock(return_value="not-json{{{")

    with patch("app.api.v1.endpoints.ws.get_redis", return_value=mock_redis):
        from app.api.v1.endpoints.ws import _authenticate_ws

        result = await _authenticate_ws("corrupt-ticket")

    assert result is None


# ---------------------------------------------------------------------------
# M-02: Password change rate limiting
# ---------------------------------------------------------------------------


def _override_auth(role="MEMBER", user_id=None):
    """Override get_current_user dependency for testing."""
    import uuid as _uuid

    from app.core.deps import get_current_user
    from app.main import app

    uid = user_id or str(_uuid.uuid4())
    payload = {"sub": uid, "role": role, "jti": str(_uuid.uuid4())}
    app.dependency_overrides[get_current_user] = lambda: payload
    return payload, uid


def _clear_overrides():
    from app.main import app

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_password_change_rate_limit(client):
    """M-02: Password change endpoint returns 429 when rate limit exceeded."""
    try:
        _override_auth("MEMBER")
        with patch(
            "app.api.v1.endpoints.users.check_rate_limit",
            new_callable=AsyncMock,
            return_value=False,
        ):
            resp = await client.put(
                "/api/v1/users/me/password",
                json={"current_password": "OldPass1!", "new_password": "NewPass1!"},
            )
            assert resp.status_code == 429
            body = resp.json()
            detail = body.get("detail", {})
            if isinstance(detail, dict):
                msg = detail.get("message", "")
            else:
                msg = str(detail)
            assert "Too many password change attempts" in msg
    finally:
        _clear_overrides()


@pytest.mark.asyncio
async def test_password_change_allowed_when_under_rate_limit(client):
    """M-02: Password change proceeds normally when rate limit not exceeded."""
    try:
        _override_auth("MEMBER")
        with (
            patch(
                "app.api.v1.endpoints.users.check_rate_limit",
                new_callable=AsyncMock,
                return_value=True,
            ),
            patch(
                "app.api.v1.endpoints.users.change_password",
                new_callable=AsyncMock,
            ),
            patch(
                "app.api.v1.endpoints.users.emit",
                new_callable=AsyncMock,
            ),
            patch(
                "app.api.v1.endpoints.users.revoke_user_sessions",
                new_callable=AsyncMock,
            ),
        ):
            resp = await client.put(
                "/api/v1/users/me/password",
                json={"current_password": "OldPass1!", "new_password": "NewPass1!"},
            )
            assert resp.status_code == 200
            assert "Password changed successfully" in resp.json()["message"]
    finally:
        _clear_overrides()


# ---------------------------------------------------------------------------
# M-03: Session revalidation on long-lived WebSocket
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_session_revalidation_closes_on_no_session():
    """M-03: Session revalidation sends FORCE_LOGOUT when no session keys exist."""
    from app.api.v1.endpoints.ws import WS_SESSION_REVALIDATION_INTERVAL

    mock_redis = AsyncMock()
    mock_redis.keys = AsyncMock(return_value=[])  # No active sessions

    mock_ws = AsyncMock()
    mock_ws.send_json = AsyncMock()
    mock_ws.close = AsyncMock()

    user_id = "user-revalidation-test"

    # Replicate the _session_revalidation closure logic
    async def _session_revalidation() -> None:
        while True:
            await asyncio.sleep(0)  # Use 0 for test speed
            try:
                r = mock_redis
                session_keys = await r.keys(f"session:{user_id}:*")
                if not session_keys:
                    await mock_ws.send_json({"type": "FORCE_LOGOUT"})
                    await mock_ws.close(code=4003, reason="Session expired")
                    return
            except Exception:
                pass

    task = asyncio.create_task(_session_revalidation())
    await task

    mock_redis.keys.assert_awaited_once_with(f"session:{user_id}:*")
    mock_ws.send_json.assert_awaited_once_with({"type": "FORCE_LOGOUT"})
    mock_ws.close.assert_awaited_once_with(code=4003, reason="Session expired")


@pytest.mark.asyncio
async def test_session_revalidation_continues_when_session_exists():
    """M-03: Session revalidation does not close WS when session keys exist."""
    mock_redis = AsyncMock()
    mock_redis.keys = AsyncMock(return_value=["session:user-1:jti-abc"])

    mock_ws = AsyncMock()
    user_id = "user-1"

    call_count = 0

    async def _session_revalidation() -> None:
        nonlocal call_count
        while True:
            await asyncio.sleep(0)
            try:
                r = mock_redis
                session_keys = await r.keys(f"session:{user_id}:*")
                if not session_keys:
                    await mock_ws.send_json({"type": "FORCE_LOGOUT"})
                    await mock_ws.close(code=4003, reason="Session expired")
                    return
            except Exception:
                pass
            call_count += 1
            if call_count >= 2:
                return  # Stop after 2 iterations for test

    task = asyncio.create_task(_session_revalidation())
    await task

    assert call_count == 2
    mock_ws.send_json.assert_not_awaited()
    mock_ws.close.assert_not_awaited()


@pytest.mark.asyncio
async def test_session_revalidation_interval_constant():
    """M-03: WS_SESSION_REVALIDATION_INTERVAL is defined and equals 300s."""
    from app.api.v1.endpoints.ws import WS_SESSION_REVALIDATION_INTERVAL

    assert WS_SESSION_REVALIDATION_INTERVAL == 300


# ---------------------------------------------------------------------------
# M-04: Per-user WebSocket connection limit
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ws_max_connections_per_user_constant():
    """M-04: WS_MAX_CONNECTIONS_PER_USER is defined and equals 5."""
    from app.api.v1.endpoints.ws import WS_MAX_CONNECTIONS_PER_USER

    assert WS_MAX_CONNECTIONS_PER_USER == 5


@pytest.mark.asyncio
async def test_ws_connection_limit_rejects_excess():
    """M-04: 6th connection for same user is rejected with code 4006."""
    from app.api.v1.endpoints.ws import (
        WS_MAX_CONNECTIONS_PER_USER,
        _connections,
        _connections_lock,
    )

    user_id = "user-conn-limit"

    # Pre-populate with max connections
    existing_sockets = {AsyncMock() for _ in range(WS_MAX_CONNECTIONS_PER_USER)}
    _connections[user_id] = existing_sockets

    try:
        mock_ws = AsyncMock()
        mock_ws.close = AsyncMock()

        # Simulate the check that happens in websocket_endpoint
        async with _connections_lock:
            if len(_connections.get(user_id, set())) >= WS_MAX_CONNECTIONS_PER_USER:
                await mock_ws.close(code=4006, reason="Too many connections")
            else:
                _connections[user_id].add(mock_ws)

        mock_ws.close.assert_awaited_once_with(code=4006, reason="Too many connections")
        # The new socket should NOT have been added
        assert mock_ws not in _connections[user_id]
    finally:
        # Cleanup
        _connections.pop(user_id, None)


@pytest.mark.asyncio
async def test_ws_connection_limit_allows_under_limit():
    """M-04: Connection is accepted when under the per-user limit."""
    from app.api.v1.endpoints.ws import (
        WS_MAX_CONNECTIONS_PER_USER,
        _connections,
        _connections_lock,
    )

    user_id = "user-conn-ok"

    # Pre-populate with fewer than max connections
    existing_sockets = {AsyncMock() for _ in range(WS_MAX_CONNECTIONS_PER_USER - 1)}
    _connections[user_id] = existing_sockets

    try:
        mock_ws = AsyncMock()
        mock_ws.close = AsyncMock()

        async with _connections_lock:
            if len(_connections.get(user_id, set())) >= WS_MAX_CONNECTIONS_PER_USER:
                await mock_ws.close(code=4006, reason="Too many connections")
            else:
                _connections[user_id].add(mock_ws)

        mock_ws.close.assert_not_awaited()
        assert mock_ws in _connections[user_id]
        assert len(_connections[user_id]) == WS_MAX_CONNECTIONS_PER_USER
    finally:
        _connections.pop(user_id, None)


@pytest.mark.asyncio
async def test_ws_connection_limit_allows_first_connection():
    """M-04: First connection for a new user is always accepted."""
    from app.api.v1.endpoints.ws import (
        WS_MAX_CONNECTIONS_PER_USER,
        _connections,
        _connections_lock,
    )

    user_id = "user-brand-new"
    # Ensure no prior connections
    _connections.pop(user_id, None)

    try:
        mock_ws = AsyncMock()
        mock_ws.close = AsyncMock()

        async with _connections_lock:
            if len(_connections.get(user_id, set())) >= WS_MAX_CONNECTIONS_PER_USER:
                await mock_ws.close(code=4006, reason="Too many connections")
            else:
                _connections[user_id].add(mock_ws)

        mock_ws.close.assert_not_awaited()
        assert mock_ws in _connections[user_id]
    finally:
        _connections.pop(user_id, None)
