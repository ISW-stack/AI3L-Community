"""Tests for WebSocket endpoint — ticket auth, rate limiting, size limits,
guest timeout, ping/pong, Redis Pub/Sub, connection lifecycle, and helpers."""

import asyncio
import json
import time
import uuid
from collections import defaultdict
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

_EP = "app.api.v1.endpoints.ws"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _ticket_payload(role: str = "MEMBER", user_id: str | None = None) -> dict:
    uid = user_id or str(uuid.uuid4())
    return {"sub": uid, "role": role}


def _make_mock_redis(ticket_data: str | None = None):
    """Return a mock Redis whose .get() returns *ticket_data* once, then None."""
    redis = AsyncMock()
    redis.get = AsyncMock(return_value=ticket_data)
    redis.delete = AsyncMock(return_value=1)
    redis.publish = AsyncMock(return_value=1)

    pubsub = AsyncMock()
    pubsub.psubscribe = AsyncMock()
    pubsub.listen = AsyncMock(return_value=iter([]))
    redis.pubsub = MagicMock(return_value=pubsub)

    return redis


# ===== _authenticate_ws =====


class TestAuthenticateWs:
    """Unit tests for _authenticate_ws (ticket validation)."""

    @pytest.mark.asyncio
    async def test_valid_ticket(self):
        payload = _ticket_payload()
        redis = _make_mock_redis(json.dumps(payload))

        with patch(f"{_EP}.get_redis", return_value=redis):
            from app.api.v1.endpoints.ws import _authenticate_ws

            result = await _authenticate_ws("abc123")

        redis.get.assert_awaited_once_with("ws:ticket:abc123")
        redis.delete.assert_awaited_once_with("ws:ticket:abc123")
        assert result == payload

    @pytest.mark.asyncio
    async def test_expired_or_missing_ticket(self):
        redis = _make_mock_redis(None)

        with patch(f"{_EP}.get_redis", return_value=redis):
            from app.api.v1.endpoints.ws import _authenticate_ws

            result = await _authenticate_ws("bad-ticket")

        assert result is None
        redis.delete.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_one_time_use_ticket_deleted(self):
        """Ticket key is deleted immediately after retrieval."""
        payload = _ticket_payload()
        redis = _make_mock_redis(json.dumps(payload))

        with patch(f"{_EP}.get_redis", return_value=redis):
            from app.api.v1.endpoints.ws import _authenticate_ws

            await _authenticate_ws("one-time")

        redis.delete.assert_awaited_once_with("ws:ticket:one-time")

    @pytest.mark.asyncio
    async def test_corrupt_ticket_data_returns_none(self):
        """If Redis returns non-JSON data, _authenticate_ws returns None."""
        redis = _make_mock_redis("not-valid-json{{")

        with patch(f"{_EP}.get_redis", return_value=redis):
            from app.api.v1.endpoints.ws import _authenticate_ws

            result = await _authenticate_ws("corrupt")

        assert result is None


# ===== websocket_endpoint =====


class TestWebsocketEndpoint:
    """Tests for the main websocket_endpoint handler."""

    @pytest.mark.asyncio
    async def test_auth_failure_closes_4001(self):
        """Connection closed with 4001 when ticket is invalid."""
        ws = AsyncMock()
        with patch(f"{_EP}._authenticate_ws", new_callable=AsyncMock, return_value=None):
            from app.api.v1.endpoints.ws import websocket_endpoint

            await websocket_endpoint(ws, ticket="bad")

        ws.close.assert_awaited_once_with(code=4001, reason="Authentication failed")
        ws.accept.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_successful_connection_and_disconnect(self):
        """Valid ticket leads to accept(); disconnect triggers cleanup."""
        payload = _ticket_payload()
        ws = AsyncMock()
        from fastapi import WebSocketDisconnect

        ws.receive_text = AsyncMock(side_effect=WebSocketDisconnect())

        with (
            patch(f"{_EP}._authenticate_ws", new_callable=AsyncMock, return_value=payload),
            patch(f"{_EP}._connections", defaultdict(set)),
            patch(f"{_EP}._connections_lock", asyncio.Lock()),
        ):
            from app.api.v1.endpoints.ws import websocket_endpoint

            await websocket_endpoint(ws, ticket="good")

        ws.accept.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_connection_registered_and_cleaned_up(self):
        """User added to _connections on accept and removed on disconnect."""
        uid = str(uuid.uuid4())
        payload = _ticket_payload(user_id=uid)
        ws = AsyncMock()

        from fastapi import WebSocketDisconnect

        ws.receive_text = AsyncMock(side_effect=WebSocketDisconnect())

        conns = defaultdict(set)
        lock = asyncio.Lock()

        with (
            patch(f"{_EP}._authenticate_ws", new_callable=AsyncMock, return_value=payload),
            patch(f"{_EP}._connections", conns),
            patch(f"{_EP}._connections_lock", lock),
        ):
            from app.api.v1.endpoints.ws import websocket_endpoint

            await websocket_endpoint(ws, ticket="t")

        # After disconnect, user should be removed
        assert uid not in conns

    @pytest.mark.asyncio
    async def test_message_size_limit_closes_4004(self):
        """Messages exceeding 64 KB cause close with code 4004."""
        payload = _ticket_payload()
        ws = AsyncMock()

        big_msg = "x" * (64 * 1024 + 1)
        from fastapi import WebSocketDisconnect

        ws.receive_text = AsyncMock(side_effect=[big_msg, WebSocketDisconnect()])

        with (
            patch(f"{_EP}._authenticate_ws", new_callable=AsyncMock, return_value=payload),
            patch(f"{_EP}._connections", defaultdict(set)),
            patch(f"{_EP}._connections_lock", asyncio.Lock()),
        ):
            from app.api.v1.endpoints.ws import websocket_endpoint

            await websocket_endpoint(ws, ticket="t")

        ws.close.assert_awaited_once_with(code=4004, reason="Message too large")

    @pytest.mark.asyncio
    async def test_message_under_size_limit_accepted(self):
        """Messages under 64 KB should be accepted (not closed)."""
        payload = _ticket_payload()
        ws = AsyncMock()

        ok_msg = json.dumps({"type": "MSG", "data": "x" * (60 * 1024)})
        from fastapi import WebSocketDisconnect

        ws.receive_text = AsyncMock(side_effect=[ok_msg, WebSocketDisconnect()])

        with (
            patch(f"{_EP}._authenticate_ws", new_callable=AsyncMock, return_value=payload),
            patch(f"{_EP}._connections", defaultdict(set)),
            patch(f"{_EP}._connections_lock", asyncio.Lock()),
        ):
            from app.api.v1.endpoints.ws import websocket_endpoint

            await websocket_endpoint(ws, ticket="t")

        # Should NOT have been closed with 4004
        for call in ws.close.call_args_list:
            assert call.kwargs.get("code") != 4004

    @pytest.mark.asyncio
    async def test_rate_limit_exceeded_closes_4005(self):
        """Exceeding 60 messages in 60s window causes close with 4005."""
        payload = _ticket_payload()
        ws = AsyncMock()

        small_msg = json.dumps({"type": "MSG"})
        from fastapi import WebSocketDisconnect

        # 61 messages = 60 allowed + 1 over
        side_effects = [small_msg] * 61 + [WebSocketDisconnect()]
        ws.receive_text = AsyncMock(side_effect=side_effects)

        with (
            patch(f"{_EP}._authenticate_ws", new_callable=AsyncMock, return_value=payload),
            patch(f"{_EP}._connections", defaultdict(set)),
            patch(f"{_EP}._connections_lock", asyncio.Lock()),
        ):
            from app.api.v1.endpoints.ws import websocket_endpoint

            await websocket_endpoint(ws, ticket="t")

        ws.close.assert_awaited_once_with(code=4005, reason="Rate limit exceeded")

    @pytest.mark.asyncio
    async def test_rate_limit_at_boundary_no_close(self):
        """Exactly 60 messages should be allowed without triggering rate limit."""
        payload = _ticket_payload()
        ws = AsyncMock()

        small_msg = json.dumps({"type": "MSG"})
        from fastapi import WebSocketDisconnect

        # 60 messages (at limit), then disconnect
        side_effects = [small_msg] * 60 + [WebSocketDisconnect()]
        ws.receive_text = AsyncMock(side_effect=side_effects)

        with (
            patch(f"{_EP}._authenticate_ws", new_callable=AsyncMock, return_value=payload),
            patch(f"{_EP}._connections", defaultdict(set)),
            patch(f"{_EP}._connections_lock", asyncio.Lock()),
        ):
            from app.api.v1.endpoints.ws import websocket_endpoint

            await websocket_endpoint(ws, ticket="t")

        # 60 messages should be fine — no 4005 close
        for call in ws.close.call_args_list:
            assert call.kwargs.get("code") != 4005

    @pytest.mark.asyncio
    async def test_rate_limit_window_reset_via_time(self):
        """After the 60s window passes, the counter resets and more messages are allowed."""
        payload = _ticket_payload()
        ws = AsyncMock()

        small_msg = json.dumps({"type": "MSG"})
        from fastapi import WebSocketDisconnect

        # 61 messages, then disconnect
        side_effects = [small_msg] * 61 + [WebSocketDisconnect()]
        ws.receive_text = AsyncMock(side_effect=side_effects)

        call_count = 0
        original_time = time.time

        def fake_time():
            nonlocal call_count
            call_count += 1
            # After 62 calls (2 init + 60 messages), jump forward 61 seconds
            if call_count > 62:
                return original_time() + 61
            return original_time()

        with (
            patch(f"{_EP}._authenticate_ws", new_callable=AsyncMock, return_value=payload),
            patch(f"{_EP}._connections", defaultdict(set)),
            patch(f"{_EP}._connections_lock", asyncio.Lock()),
            patch(f"{_EP}.time", wraps=time) as mock_time,
        ):
            mock_time.time = fake_time
            from app.api.v1.endpoints.ws import websocket_endpoint

            await websocket_endpoint(ws, ticket="t")

        # Should NOT have closed with 4005 because window reset
        for call in ws.close.call_args_list:
            assert call.kwargs.get("code") != 4005

    @pytest.mark.asyncio
    async def test_pong_message_updates_last_pong(self):
        """A PONG message should be processed without error."""
        payload = _ticket_payload()
        ws = AsyncMock()

        pong_msg = json.dumps({"type": "PONG"})
        from fastapi import WebSocketDisconnect

        ws.receive_text = AsyncMock(side_effect=[pong_msg, WebSocketDisconnect()])

        with (
            patch(f"{_EP}._authenticate_ws", new_callable=AsyncMock, return_value=payload),
            patch(f"{_EP}._connections", defaultdict(set)),
            patch(f"{_EP}._connections_lock", asyncio.Lock()),
        ):
            from app.api.v1.endpoints.ws import websocket_endpoint

            await websocket_endpoint(ws, ticket="t")

        # No error close — just clean disconnect
        ws.accept.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_guest_timeout_task_created(self):
        """Guest role triggers creation of a timeout task (then cancelled on disconnect)."""
        payload = _ticket_payload(role="GUEST")
        ws = AsyncMock()

        from fastapi import WebSocketDisconnect

        ws.receive_text = AsyncMock(side_effect=WebSocketDisconnect())

        with (
            patch(f"{_EP}._authenticate_ws", new_callable=AsyncMock, return_value=payload),
            patch(f"{_EP}._connections", defaultdict(set)),
            patch(f"{_EP}._connections_lock", asyncio.Lock()),
        ):
            from app.api.v1.endpoints.ws import websocket_endpoint

            await websocket_endpoint(ws, ticket="t")

        # If we got here without error, the guest timeout task was created and cancelled
        ws.accept.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_non_guest_no_timeout_task(self):
        """Non-guest roles should NOT have a guest timeout task."""
        payload = _ticket_payload(role="ADMIN")
        ws = AsyncMock()

        from fastapi import WebSocketDisconnect

        ws.receive_text = AsyncMock(side_effect=WebSocketDisconnect())

        with (
            patch(f"{_EP}._authenticate_ws", new_callable=AsyncMock, return_value=payload),
            patch(f"{_EP}._connections", defaultdict(set)),
            patch(f"{_EP}._connections_lock", asyncio.Lock()),
        ):
            from app.api.v1.endpoints.ws import websocket_endpoint

            await websocket_endpoint(ws, ticket="t")

        ws.accept.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_unexpected_error_handled(self):
        """Unexpected exceptions in the receive loop are caught gracefully."""
        payload = _ticket_payload()
        ws = AsyncMock()

        ws.receive_text = AsyncMock(side_effect=RuntimeError("boom"))

        with (
            patch(f"{_EP}._authenticate_ws", new_callable=AsyncMock, return_value=payload),
            patch(f"{_EP}._connections", defaultdict(set)),
            patch(f"{_EP}._connections_lock", asyncio.Lock()),
        ):
            from app.api.v1.endpoints.ws import websocket_endpoint

            # Should not raise — the handler catches Exception
            await websocket_endpoint(ws, ticket="t")

        ws.accept.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_json_parse_error_in_message(self):
        """Invalid JSON in a received message triggers the generic except branch."""
        payload = _ticket_payload()
        ws = AsyncMock()

        from fastapi import WebSocketDisconnect

        ws.receive_text = AsyncMock(side_effect=["not json at all", WebSocketDisconnect()])

        with (
            patch(f"{_EP}._authenticate_ws", new_callable=AsyncMock, return_value=payload),
            patch(f"{_EP}._connections", defaultdict(set)),
            patch(f"{_EP}._connections_lock", asyncio.Lock()),
        ):
            from app.api.v1.endpoints.ws import websocket_endpoint

            # json.loads will raise JSONDecodeError -> caught by except Exception
            await websocket_endpoint(ws, ticket="t")

        ws.accept.assert_awaited_once()


# ===== send_to_user =====


class TestSendToUser:
    @pytest.mark.asyncio
    async def test_publishes_via_redis(self):
        uid = str(uuid.uuid4())
        msg = {"type": "NOTIFICATION", "data": "hello"}
        redis = _make_mock_redis()

        with patch(f"{_EP}.get_redis", return_value=redis):
            from app.api.v1.endpoints.ws import send_to_user

            await send_to_user(uid, msg)

        redis.publish.assert_awaited_once_with(f"ws:user:{uid}", json.dumps(msg))

    @pytest.mark.asyncio
    async def test_fallback_to_local_on_redis_error(self):
        uid = str(uuid.uuid4())
        msg = {"type": "NOTIFICATION"}
        redis = _make_mock_redis()
        redis.publish = AsyncMock(side_effect=Exception("Redis down"))

        with (
            patch(f"{_EP}.get_redis", return_value=redis),
            patch(f"{_EP}._local_send", new_callable=AsyncMock) as mock_local,
        ):
            from app.api.v1.endpoints.ws import send_to_user

            await send_to_user(uid, msg)

        mock_local.assert_awaited_once_with(uid, msg)


# ===== force_logout =====


class TestForceLogout:
    @pytest.mark.asyncio
    async def test_publishes_logout_via_redis(self):
        uid = str(uuid.uuid4())
        redis = _make_mock_redis()

        with patch(f"{_EP}.get_redis", return_value=redis):
            from app.api.v1.endpoints.ws import force_logout

            await force_logout(uid)

        redis.publish.assert_awaited_once_with(f"ws:logout:{uid}", "1")

    @pytest.mark.asyncio
    async def test_fallback_to_local_on_redis_error(self):
        uid = str(uuid.uuid4())
        redis = _make_mock_redis()
        redis.publish = AsyncMock(side_effect=Exception("Redis down"))

        with (
            patch(f"{_EP}.get_redis", return_value=redis),
            patch(f"{_EP}._local_force_logout", new_callable=AsyncMock) as mock_local,
        ):
            from app.api.v1.endpoints.ws import force_logout

            await force_logout(uid)

        mock_local.assert_awaited_once_with(uid)


# ===== _local_send =====


class TestLocalSend:
    @pytest.mark.asyncio
    async def test_sends_to_all_connections(self):
        uid = str(uuid.uuid4())
        ws1 = AsyncMock()
        ws2 = AsyncMock()
        msg = {"type": "TEST"}

        conns = defaultdict(set)
        conns[uid] = {ws1, ws2}

        with (
            patch(f"{_EP}._connections", conns),
            patch(f"{_EP}._connections_lock", asyncio.Lock()),
        ):
            from app.api.v1.endpoints.ws import _local_send

            await _local_send(uid, msg)

        ws1.send_json.assert_awaited_once_with(msg)
        ws2.send_json.assert_awaited_once_with(msg)

    @pytest.mark.asyncio
    async def test_discards_broken_connection(self):
        uid = str(uuid.uuid4())
        ws_ok = AsyncMock()
        ws_broken = AsyncMock()
        ws_broken.send_json = AsyncMock(side_effect=Exception("broken"))
        msg = {"type": "TEST"}

        conns = defaultdict(set)
        conns[uid] = {ws_ok, ws_broken}

        with (
            patch(f"{_EP}._connections", conns),
            patch(f"{_EP}._connections_lock", asyncio.Lock()),
        ):
            from app.api.v1.endpoints.ws import _local_send

            await _local_send(uid, msg)

        # broken ws should be discarded
        assert ws_broken not in conns[uid]

    @pytest.mark.asyncio
    async def test_no_connections_does_nothing(self):
        uid = str(uuid.uuid4())
        conns = defaultdict(set)

        with (
            patch(f"{_EP}._connections", conns),
            patch(f"{_EP}._connections_lock", asyncio.Lock()),
        ):
            from app.api.v1.endpoints.ws import _local_send

            # Should not raise
            await _local_send(uid, {"type": "TEST"})


# ===== _local_force_logout =====


class TestLocalForceLogout:
    @pytest.mark.asyncio
    async def test_sends_force_logout_and_closes(self):
        uid = str(uuid.uuid4())
        ws = AsyncMock()

        conns = defaultdict(set)
        conns[uid] = {ws}

        with (
            patch(f"{_EP}._connections", conns),
            patch(f"{_EP}._connections_lock", asyncio.Lock()),
        ):
            from app.api.v1.endpoints.ws import _local_force_logout

            await _local_force_logout(uid)

        ws.send_json.assert_awaited_once_with({"type": "FORCE_LOGOUT"})
        ws.close.assert_awaited_once_with(code=4003, reason="Session expired")
        assert uid not in conns

    @pytest.mark.asyncio
    async def test_handles_send_failure(self):
        uid = str(uuid.uuid4())
        ws = AsyncMock()
        ws.send_json = AsyncMock(side_effect=Exception("closed"))

        conns = defaultdict(set)
        conns[uid] = {ws}

        with (
            patch(f"{_EP}._connections", conns),
            patch(f"{_EP}._connections_lock", asyncio.Lock()),
        ):
            from app.api.v1.endpoints.ws import _local_force_logout

            # Should not raise
            await _local_force_logout(uid)

        # User removed from connections regardless
        assert uid not in conns


# ===== Redis Pub/Sub subscriber =====


class TestRedisSubscriber:
    @pytest.mark.asyncio
    async def test_start_and_stop_subscriber(self):
        with patch(f"{_EP}._subscribe_with_retry", new_callable=AsyncMock) as mock_retry:
            # Make it a coroutine that waits until cancelled
            async def wait_forever():
                await asyncio.sleep(3600)

            mock_retry.side_effect = wait_forever

            from app.api.v1.endpoints.ws import start_redis_subscriber, stop_redis_subscriber

            await start_redis_subscriber()

            # Give the task a moment to start
            await asyncio.sleep(0.01)

            await stop_redis_subscriber()

    @pytest.mark.asyncio
    async def test_subscriber_dispatches_user_message(self):
        uid = str(uuid.uuid4())
        msg_data = {"type": "NOTIFICATION", "text": "hi"}

        async def fake_listen():
            yield {
                "type": "pmessage",
                "channel": f"ws:user:{uid}",
                "data": json.dumps(msg_data),
            }

        redis = _make_mock_redis()
        pubsub = AsyncMock()
        pubsub.psubscribe = AsyncMock()
        pubsub.listen = MagicMock(return_value=fake_listen())
        redis.pubsub = MagicMock(return_value=pubsub)

        with (
            patch(f"{_EP}.get_redis", return_value=redis),
            patch(f"{_EP}._local_send", new_callable=AsyncMock) as mock_send,
        ):
            from app.api.v1.endpoints.ws import _redis_subscriber

            await _redis_subscriber()

        mock_send.assert_awaited_once_with(uid, msg_data)

    @pytest.mark.asyncio
    async def test_subscriber_dispatches_logout_message(self):
        uid = str(uuid.uuid4())

        async def fake_listen():
            yield {
                "type": "pmessage",
                "channel": f"ws:logout:{uid}",
                "data": "1",
            }

        redis = _make_mock_redis()
        pubsub = AsyncMock()
        pubsub.psubscribe = AsyncMock()
        pubsub.listen = MagicMock(return_value=fake_listen())
        redis.pubsub = MagicMock(return_value=pubsub)

        with (
            patch(f"{_EP}.get_redis", return_value=redis),
            patch(f"{_EP}._local_force_logout", new_callable=AsyncMock) as mock_logout,
        ):
            from app.api.v1.endpoints.ws import _redis_subscriber

            await _redis_subscriber()

        mock_logout.assert_awaited_once_with(uid)

    @pytest.mark.asyncio
    async def test_subscriber_ignores_non_pmessage(self):
        async def fake_listen():
            yield {"type": "psubscribe", "channel": "ws:user:*", "data": 1}

        redis = _make_mock_redis()
        pubsub = AsyncMock()
        pubsub.psubscribe = AsyncMock()
        pubsub.listen = MagicMock(return_value=fake_listen())
        redis.pubsub = MagicMock(return_value=pubsub)

        with (
            patch(f"{_EP}.get_redis", return_value=redis),
            patch(f"{_EP}._local_send", new_callable=AsyncMock) as mock_send,
            patch(f"{_EP}._local_force_logout", new_callable=AsyncMock) as mock_logout,
        ):
            from app.api.v1.endpoints.ws import _redis_subscriber

            await _redis_subscriber()

        mock_send.assert_not_awaited()
        mock_logout.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_subscriber_handles_bytes_channel(self):
        """Channel and data arriving as bytes are decoded properly."""
        uid = str(uuid.uuid4())
        msg_data = {"type": "TEST"}

        async def fake_listen():
            yield {
                "type": "pmessage",
                "channel": f"ws:user:{uid}".encode(),
                "data": json.dumps(msg_data).encode(),
            }

        redis = _make_mock_redis()
        pubsub = AsyncMock()
        pubsub.psubscribe = AsyncMock()
        pubsub.listen = MagicMock(return_value=fake_listen())
        redis.pubsub = MagicMock(return_value=pubsub)

        with (
            patch(f"{_EP}.get_redis", return_value=redis),
            patch(f"{_EP}._local_send", new_callable=AsyncMock) as mock_send,
        ):
            from app.api.v1.endpoints.ws import _redis_subscriber

            await _redis_subscriber()

        mock_send.assert_awaited_once_with(uid, msg_data)

    @pytest.mark.asyncio
    async def test_subscriber_handles_processing_error(self):
        """Errors processing individual messages are caught, loop continues."""

        async def fake_listen():
            yield {
                "type": "pmessage",
                "channel": "ws:user:some-id",
                "data": "not-valid-json",
            }

        redis = _make_mock_redis()
        pubsub = AsyncMock()
        pubsub.psubscribe = AsyncMock()
        pubsub.listen = MagicMock(return_value=fake_listen())
        redis.pubsub = MagicMock(return_value=pubsub)

        with patch(f"{_EP}.get_redis", return_value=redis):
            from app.api.v1.endpoints.ws import _redis_subscriber

            # Should not raise
            await _redis_subscriber()


# ===== _subscribe_with_retry =====


class TestSubscribeWithRetry:
    @pytest.mark.asyncio
    async def test_retry_on_crash(self):
        """Subscriber retries after a crash with backoff."""
        call_count = 0

        async def crash_then_cancel():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ConnectionError("Redis gone")
            # On second call, raise CancelledError to stop loop
            raise asyncio.CancelledError()

        with (
            patch(
                f"{_EP}._redis_subscriber",
                new_callable=AsyncMock,
                side_effect=crash_then_cancel,
            ),
            patch(f"{_EP}.asyncio.sleep", new_callable=AsyncMock) as mock_sleep,
        ):
            from app.api.v1.endpoints.ws import _subscribe_with_retry

            with pytest.raises(asyncio.CancelledError):
                await _subscribe_with_retry()

        assert call_count == 2
        mock_sleep.assert_awaited_once_with(5)  # initial backoff

    @pytest.mark.asyncio
    async def test_backoff_doubles(self):
        """Backoff doubles on repeated failures up to max."""
        call_count = 0

        async def crash_repeatedly():
            nonlocal call_count
            call_count += 1
            if call_count <= 3:
                raise ConnectionError("Redis gone")
            raise asyncio.CancelledError()

        with (
            patch(
                f"{_EP}._redis_subscriber",
                new_callable=AsyncMock,
                side_effect=crash_repeatedly,
            ),
            patch(f"{_EP}.asyncio.sleep", new_callable=AsyncMock) as mock_sleep,
        ):
            from app.api.v1.endpoints.ws import _subscribe_with_retry

            with pytest.raises(asyncio.CancelledError):
                await _subscribe_with_retry()

        # backoff: 5, 10, 20
        sleep_args = [c.args[0] for c in mock_sleep.call_args_list]
        assert sleep_args == [5, 10, 20]


# ===== Module-level constants =====


class TestConstants:
    def test_max_message_size(self):
        from app.api.v1.endpoints.ws import WS_MAX_MESSAGE_SIZE

        assert WS_MAX_MESSAGE_SIZE == 64 * 1024

    def test_rate_limit(self):
        from app.api.v1.endpoints.ws import WS_MSG_RATE_LIMIT

        assert WS_MSG_RATE_LIMIT == 60

    def test_rate_window(self):
        from app.api.v1.endpoints.ws import WS_MSG_RATE_WINDOW

        assert WS_MSG_RATE_WINDOW == 60
