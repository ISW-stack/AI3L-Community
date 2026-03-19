"""Tests for bug fixes N-B01, N-B04, N-B05, N-B18.

N-B01: WebSocket json.loads targeted error handling
N-B04: view_sync reconciliation wrapped in transactions
N-B05: SIG notification pagination uses batch-size termination
N-B18: Idempotency middleware skips caching 5xx and 429 responses
"""

import asyncio
import json
import uuid
from collections import defaultdict
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# N-B01: WebSocket JSONDecodeError handling
# ---------------------------------------------------------------------------

_EP = "app.api.v1.endpoints.ws"


def _ticket_payload(role: str = "MEMBER", user_id: str | None = None) -> dict:
    uid = user_id or str(uuid.uuid4())
    return {"sub": uid, "role": role}


class TestWebSocketJSONDecodeError:
    """N-B01: Invalid JSON should send error response and continue, not disconnect."""

    @pytest.mark.asyncio
    async def test_invalid_json_sends_error_and_continues(self):
        """Invalid JSON triggers an error reply; the loop continues for the next message."""
        payload = _ticket_payload()
        ws = AsyncMock()

        from fastapi import WebSocketDisconnect

        good_msg = json.dumps({"type": "MSG"})
        ws.receive_text = AsyncMock(side_effect=["not valid json", good_msg, WebSocketDisconnect()])

        with (
            patch(f"{_EP}._authenticate_ws", new_callable=AsyncMock, return_value=payload),
            patch(f"{_EP}._connections", defaultdict(set)),
            patch(f"{_EP}._connections_lock", asyncio.Lock()),
        ):
            from app.api.v1.endpoints.ws import websocket_endpoint

            await websocket_endpoint(ws, ticket="t")

        # Should have sent an error response for the invalid JSON
        ws.send_json.assert_any_call({"error": "invalid_json"})
        # Should NOT have been closed with an error code
        for call in ws.close.call_args_list:
            assert call.kwargs.get("code") not in (4004, 4005)

    @pytest.mark.asyncio
    async def test_invalid_json_does_not_consume_rate_limit(self):
        """Invalid JSON messages should not increment the rate limit counter."""
        payload = _ticket_payload()
        ws = AsyncMock()

        from fastapi import WebSocketDisconnect

        # Send 60 invalid JSONs + 1 valid JSON — should NOT trigger rate limit
        side_effects = ["bad json"] * 60 + [json.dumps({"type": "MSG"})] + [WebSocketDisconnect()]
        ws.receive_text = AsyncMock(side_effect=side_effects)

        with (
            patch(f"{_EP}._authenticate_ws", new_callable=AsyncMock, return_value=payload),
            patch(f"{_EP}._connections", defaultdict(set)),
            patch(f"{_EP}._connections_lock", asyncio.Lock()),
        ):
            from app.api.v1.endpoints.ws import websocket_endpoint

            await websocket_endpoint(ws, ticket="t")

        # Should NOT have been closed with rate limit code 4005
        for call in ws.close.call_args_list:
            assert call.kwargs.get("code") != 4005

    @pytest.mark.asyncio
    async def test_invalid_json_logs_debug(self):
        """Invalid JSON should log a debug message."""
        payload = _ticket_payload()
        ws = AsyncMock()

        from fastapi import WebSocketDisconnect

        ws.receive_text = AsyncMock(side_effect=["{{invalid", WebSocketDisconnect()])

        with (
            patch(f"{_EP}._authenticate_ws", new_callable=AsyncMock, return_value=payload),
            patch(f"{_EP}._connections", defaultdict(set)),
            patch(f"{_EP}._connections_lock", asyncio.Lock()),
            patch(f"{_EP}.logger") as mock_logger,
        ):
            from app.api.v1.endpoints.ws import websocket_endpoint

            await websocket_endpoint(ws, ticket="t")

        mock_logger.debug.assert_called()
        debug_msg = mock_logger.debug.call_args.args[0]
        assert "Invalid JSON" in debug_msg

    @pytest.mark.asyncio
    async def test_invalid_json_send_error_failure_does_not_crash(self):
        """If sending the error response fails, the loop should still continue."""
        payload = _ticket_payload()
        ws = AsyncMock()

        from fastapi import WebSocketDisconnect

        good_msg = json.dumps({"type": "PONG"})
        ws.receive_text = AsyncMock(side_effect=["bad", good_msg, WebSocketDisconnect()])
        # send_json fails on the error reply
        ws.send_json = AsyncMock(side_effect=[Exception("write failed"), None])

        with (
            patch(f"{_EP}._authenticate_ws", new_callable=AsyncMock, return_value=payload),
            patch(f"{_EP}._connections", defaultdict(set)),
            patch(f"{_EP}._connections_lock", asyncio.Lock()),
        ):
            from app.api.v1.endpoints.ws import websocket_endpoint

            await websocket_endpoint(ws, ticket="t")

        # Should have accepted and processed the good PONG message after the bad one
        ws.accept.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_multiple_invalid_json_messages_continue(self):
        """Multiple consecutive invalid JSON messages are handled without disconnect."""
        payload = _ticket_payload()
        ws = AsyncMock()

        from fastapi import WebSocketDisconnect

        ws.receive_text = AsyncMock(side_effect=["bad1", "bad2", "bad3", WebSocketDisconnect()])

        with (
            patch(f"{_EP}._authenticate_ws", new_callable=AsyncMock, return_value=payload),
            patch(f"{_EP}._connections", defaultdict(set)),
            patch(f"{_EP}._connections_lock", asyncio.Lock()),
        ):
            from app.api.v1.endpoints.ws import websocket_endpoint

            await websocket_endpoint(ws, ticket="t")

        # Three error responses should have been sent
        assert ws.send_json.call_count == 3
        for call in ws.send_json.call_args_list:
            assert call.args[0] == {"error": "invalid_json"}


# ---------------------------------------------------------------------------
# N-B04: view_sync reconciliation wrapped in transactions
# ---------------------------------------------------------------------------

_VIEW_SYNC = "app.tasks.view_sync"


class TestViewSyncTransactions:
    """N-B04: Each reconciliation function wraps UPDATE + zero-out in a transaction."""

    @pytest.mark.asyncio
    async def test_citation_counts_uses_transaction(self):
        """_reconcile_citation_counts wraps both statements in a transaction."""
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock(return_value="UPDATE 5")

        mock_tx = AsyncMock()
        mock_tx.__aenter__ = AsyncMock(return_value=mock_tx)
        mock_tx.__aexit__ = AsyncMock(return_value=False)
        mock_conn.transaction = MagicMock(return_value=mock_tx)

        mock_pool = AsyncMock()
        mock_pool.acquire = MagicMock(
            return_value=AsyncMock(
                __aenter__=AsyncMock(return_value=mock_conn),
                __aexit__=AsyncMock(return_value=False),
            )
        )

        with patch(f"{_VIEW_SYNC}.get_pool", return_value=mock_pool):
            from app.tasks.view_sync import _reconcile_citation_counts

            result = await _reconcile_citation_counts()

        assert result == 5
        mock_conn.transaction.assert_called_once()
        # Two execute calls: UPDATE + zero-out
        assert mock_conn.execute.await_count == 2

    @pytest.mark.asyncio
    async def test_answer_counts_uses_transaction(self):
        """_reconcile_answer_counts wraps both statements in a transaction."""
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock(return_value="UPDATE 3")

        mock_tx = AsyncMock()
        mock_tx.__aenter__ = AsyncMock(return_value=mock_tx)
        mock_tx.__aexit__ = AsyncMock(return_value=False)
        mock_conn.transaction = MagicMock(return_value=mock_tx)

        mock_pool = AsyncMock()
        mock_pool.acquire = MagicMock(
            return_value=AsyncMock(
                __aenter__=AsyncMock(return_value=mock_conn),
                __aexit__=AsyncMock(return_value=False),
            )
        )

        with patch(f"{_VIEW_SYNC}.get_pool", return_value=mock_pool):
            from app.tasks.view_sync import _reconcile_answer_counts

            result = await _reconcile_answer_counts()

        assert result == 3
        mock_conn.transaction.assert_called_once()
        assert mock_conn.execute.await_count == 2

    @pytest.mark.asyncio
    async def test_vote_scores_uses_transaction(self):
        """_reconcile_vote_scores wraps both statements in a transaction."""
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock(return_value="UPDATE 7")

        mock_tx = AsyncMock()
        mock_tx.__aenter__ = AsyncMock(return_value=mock_tx)
        mock_tx.__aexit__ = AsyncMock(return_value=False)
        mock_conn.transaction = MagicMock(return_value=mock_tx)

        mock_pool = AsyncMock()
        mock_pool.acquire = MagicMock(
            return_value=AsyncMock(
                __aenter__=AsyncMock(return_value=mock_conn),
                __aexit__=AsyncMock(return_value=False),
            )
        )

        with patch(f"{_VIEW_SYNC}.get_pool", return_value=mock_pool):
            from app.tasks.view_sync import _reconcile_vote_scores

            result = await _reconcile_vote_scores()

        assert result == 7
        mock_conn.transaction.assert_called_once()
        assert mock_conn.execute.await_count == 2

    @pytest.mark.asyncio
    async def test_profile_view_counts_uses_transaction(self):
        """_reconcile_profile_view_counts wraps all statements in a transaction."""
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock(return_value="UPDATE 2")

        mock_tx = AsyncMock()
        mock_tx.__aenter__ = AsyncMock(return_value=mock_tx)
        mock_tx.__aexit__ = AsyncMock(return_value=False)
        mock_conn.transaction = MagicMock(return_value=mock_tx)

        mock_pool = AsyncMock()
        mock_pool.acquire = MagicMock(
            return_value=AsyncMock(
                __aenter__=AsyncMock(return_value=mock_conn),
                __aexit__=AsyncMock(return_value=False),
            )
        )

        with patch(f"{_VIEW_SYNC}.get_pool", return_value=mock_pool):
            from app.tasks.view_sync import _reconcile_profile_view_counts

            unique, total = await _reconcile_profile_view_counts()

        assert unique == 2
        assert total == 2
        mock_conn.transaction.assert_called_once()
        # Two execute calls: unique + total
        assert mock_conn.execute.await_count == 2

    @pytest.mark.asyncio
    async def test_transaction_rollback_on_error(self):
        """If the zero-out query fails, the transaction should roll back."""
        call_count = 0

        async def _execute_side_effect(sql):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return "UPDATE 5"
            raise RuntimeError("DB error during zero-out")

        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock(side_effect=_execute_side_effect)

        mock_tx = AsyncMock()
        mock_tx.__aenter__ = AsyncMock(return_value=mock_tx)
        mock_tx.__aexit__ = AsyncMock(return_value=False)
        mock_conn.transaction = MagicMock(return_value=mock_tx)

        mock_pool = AsyncMock()
        mock_pool.acquire = MagicMock(
            return_value=AsyncMock(
                __aenter__=AsyncMock(return_value=mock_conn),
                __aexit__=AsyncMock(return_value=False),
            )
        )

        with patch(f"{_VIEW_SYNC}.get_pool", return_value=mock_pool):
            from app.tasks.view_sync import _reconcile_citation_counts

            with pytest.raises(RuntimeError, match="DB error during zero-out"):
                await _reconcile_citation_counts()


# ---------------------------------------------------------------------------
# N-B05: SIG notification pagination uses batch-size termination
# ---------------------------------------------------------------------------


def _make_member(user_id: str | None = None) -> dict:
    return {"user_id": uuid.UUID(user_id) if user_id else uuid.uuid4()}


class TestSigNotificationPagination:
    """N-B05: Pagination terminates based on batch size, not stale total."""

    @pytest.mark.asyncio
    async def test_terminates_on_short_batch(self):
        """Loop stops when batch size < page size (last page)."""
        author_id = str(uuid.uuid4())
        sig_id = str(uuid.uuid4())
        post_id = str(uuid.uuid4())

        # Batch 1: 200 members (full), Batch 2: 50 members (short — last page)
        batch1 = [_make_member() for _ in range(200)]
        batch2 = [_make_member() for _ in range(50)]

        call_count = 0

        async def _find_members(sid, offset=0, limit=200):
            nonlocal call_count
            call_count += 1
            if offset == 0:
                return (batch1, 999)  # stale total
            return (batch2, 999)

        mock_get_user = AsyncMock(return_value={"display_name": "Author"})
        mock_create = AsyncMock()
        mock_check = AsyncMock(return_value=True)

        with (
            patch("app.repositories.sig_repo.find_members", AsyncMock(side_effect=_find_members)),
            patch("app.services.user.get_user_by_id", mock_get_user),
            patch("app.services.notification.create_notification", mock_create),
            patch("app.event_handlers._check_idempotent", mock_check),
        ):
            from app.event_handlers import _on_post_created_in_sig

            await _on_post_created_in_sig(
                sig_id=sig_id,
                post_id=post_id,
                author_id=author_id,
                post_title="Test",
            )

        # Should have queried exactly 2 batches
        assert call_count == 2
        # Total notifications = 250 members (none is the author)
        assert mock_create.await_count == 250

    @pytest.mark.asyncio
    async def test_does_not_use_stale_total_to_stop_early(self):
        """Even with a low total from first query, all batches are fetched."""
        author_id = str(uuid.uuid4())
        sig_id = str(uuid.uuid4())
        post_id = str(uuid.uuid4())

        # Two full batches, then empty. total=100 in first response is stale.
        batch1 = [_make_member() for _ in range(200)]
        batch2 = [_make_member() for _ in range(200)]

        async def _find_members(sid, offset=0, limit=200):
            if offset == 0:
                return (batch1, 100)  # stale: says 100 but there are 400
            elif offset == 200:
                return (batch2, 400)
            return ([], 400)

        mock_get_user = AsyncMock(return_value={"display_name": "Author"})
        mock_create = AsyncMock()
        mock_check = AsyncMock(return_value=True)

        with (
            patch("app.repositories.sig_repo.find_members", AsyncMock(side_effect=_find_members)),
            patch("app.services.user.get_user_by_id", mock_get_user),
            patch("app.services.notification.create_notification", mock_create),
            patch("app.event_handlers._check_idempotent", mock_check),
        ):
            from app.event_handlers import _on_post_created_in_sig

            await _on_post_created_in_sig(
                sig_id=sig_id,
                post_id=post_id,
                author_id=author_id,
                post_title="Test",
            )

        # All 400 members should be notified (old code would stop at offset 100)
        assert mock_create.await_count == 400

    @pytest.mark.asyncio
    async def test_terminates_on_empty_batch(self):
        """Loop stops when an empty batch is returned."""
        author_id = str(uuid.uuid4())
        sig_id = str(uuid.uuid4())
        post_id = str(uuid.uuid4())

        batch1 = [_make_member() for _ in range(200)]

        call_count = 0

        async def _find_members(sid, offset=0, limit=200):
            nonlocal call_count
            call_count += 1
            if offset == 0:
                return (batch1, 200)
            return ([], 200)

        mock_get_user = AsyncMock(return_value={"display_name": "Author"})
        mock_create = AsyncMock()
        mock_check = AsyncMock(return_value=True)

        with (
            patch("app.repositories.sig_repo.find_members", AsyncMock(side_effect=_find_members)),
            patch("app.services.user.get_user_by_id", mock_get_user),
            patch("app.services.notification.create_notification", mock_create),
            patch("app.event_handlers._check_idempotent", mock_check),
        ):
            from app.event_handlers import _on_post_created_in_sig

            await _on_post_created_in_sig(
                sig_id=sig_id,
                post_id=post_id,
                author_id=author_id,
                post_title="Test",
            )

        # First batch is full size (200), so loop continues; second is empty, so stops
        assert call_count == 2
        assert mock_create.await_count == 200

    @pytest.mark.asyncio
    async def test_single_partial_batch(self):
        """A SIG with fewer members than page size fetches exactly one batch."""
        author_id = str(uuid.uuid4())
        sig_id = str(uuid.uuid4())
        post_id = str(uuid.uuid4())

        members = [_make_member() for _ in range(10)]

        mock_find = AsyncMock(return_value=(members, 10))
        mock_get_user = AsyncMock(return_value={"display_name": "Author"})
        mock_create = AsyncMock()
        mock_check = AsyncMock(return_value=True)

        with (
            patch("app.repositories.sig_repo.find_members", mock_find),
            patch("app.services.user.get_user_by_id", mock_get_user),
            patch("app.services.notification.create_notification", mock_create),
            patch("app.event_handlers._check_idempotent", mock_check),
        ):
            from app.event_handlers import _on_post_created_in_sig

            await _on_post_created_in_sig(
                sig_id=sig_id,
                post_id=post_id,
                author_id=author_id,
                post_title="Test",
            )

        mock_find.assert_awaited_once()
        assert mock_create.await_count == 10


# ---------------------------------------------------------------------------
# N-B18: Idempotency middleware skips caching 5xx and 429 responses
# ---------------------------------------------------------------------------

_IDEM = "app.middleware.idempotency"


def _make_streaming_response(body_dict: dict, status_code: int) -> MagicMock:
    """Create a mock response with body_iterator like BaseHTTPMiddleware produces."""
    body_bytes = json.dumps(body_dict).encode()

    async def _body_iter():
        yield body_bytes

    resp = MagicMock()
    resp.status_code = status_code
    resp.headers = {"content-type": "application/json"}
    resp.body_iterator = _body_iter()
    return resp


def _make_request_scope(idem_key: str) -> dict:
    return {
        "type": "http",
        "method": "POST",
        "path": "/api/v1/posts",
        "headers": [
            (b"idempotency-key", idem_key.encode()),
            (b"authorization", b"Bearer faketoken"),
            (b"content-type", b"application/json"),
        ],
        "query_string": b"",
    }


class TestIdempotencyNoCacheTransientErrors:
    """N-B18: 5xx and 429 responses should NOT be cached."""

    @pytest.mark.asyncio
    async def test_500_response_not_cached(self):
        """A 500 error response should not be stored in Redis."""
        from starlette.requests import Request

        from app.middleware.idempotency import IdempotencyMiddleware

        middleware = IdempotencyMiddleware(app=AsyncMock())

        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=None)
        mock_redis.set = AsyncMock(return_value=True)
        mock_redis.delete = AsyncMock()

        request = Request(_make_request_scope("test-key-500"))

        async def call_next(req):
            return _make_streaming_response({"detail": "Internal Server Error"}, 500)

        with patch(f"{_IDEM}.get_redis", return_value=mock_redis):
            response = await middleware.dispatch(request, call_next)

        assert response.status_code == 500
        # The processing marker should be deleted (not replaced with cached response)
        mock_redis.delete.assert_awaited_once()
        # Redis.set should only have the processing marker, NOT the 500 response
        set_calls = mock_redis.set.call_args_list
        for call in set_calls:
            if len(call.args) >= 2:
                data = call.args[1]
                if isinstance(data, str) and "status_code" in data:
                    pytest.fail("500 response should not be cached")

    @pytest.mark.asyncio
    async def test_429_response_not_cached(self):
        """A 429 rate limit response should not be stored in Redis."""
        from starlette.requests import Request

        from app.middleware.idempotency import IdempotencyMiddleware

        middleware = IdempotencyMiddleware(app=AsyncMock())

        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=None)
        mock_redis.set = AsyncMock(return_value=True)
        mock_redis.delete = AsyncMock()

        request = Request(_make_request_scope("test-key-429"))

        async def call_next(req):
            return _make_streaming_response({"detail": "Rate limit exceeded"}, 429)

        with patch(f"{_IDEM}.get_redis", return_value=mock_redis):
            response = await middleware.dispatch(request, call_next)

        assert response.status_code == 429
        mock_redis.delete.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_503_response_not_cached(self):
        """A 503 Service Unavailable response should not be cached."""
        from starlette.requests import Request

        from app.middleware.idempotency import IdempotencyMiddleware

        middleware = IdempotencyMiddleware(app=AsyncMock())

        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=None)
        mock_redis.set = AsyncMock(return_value=True)
        mock_redis.delete = AsyncMock()

        request = Request(_make_request_scope("test-key-503"))

        async def call_next(req):
            return _make_streaming_response({"detail": "Service Unavailable"}, 503)

        with patch(f"{_IDEM}.get_redis", return_value=mock_redis):
            response = await middleware.dispatch(request, call_next)

        assert response.status_code == 503
        mock_redis.delete.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_200_response_is_cached(self):
        """A 200 success response should be cached normally."""
        from starlette.requests import Request

        from app.middleware.idempotency import IdempotencyMiddleware

        middleware = IdempotencyMiddleware(app=AsyncMock())

        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=None)
        mock_redis.set = AsyncMock(return_value=True)

        request = Request(_make_request_scope("test-key-200"))

        async def call_next(req):
            return _make_streaming_response({"id": "123"}, 200)

        with patch(f"{_IDEM}.get_redis", return_value=mock_redis):
            response = await middleware.dispatch(request, call_next)

        assert response.status_code == 200
        # Should have two set calls: processing marker + cache
        assert mock_redis.set.await_count == 2
        # The second set call should contain the cached response
        cache_call = mock_redis.set.call_args_list[1]
        cached_data = json.loads(cache_call.args[1])
        assert cached_data["status_code"] == 200

    @pytest.mark.asyncio
    async def test_400_response_is_cached(self):
        """A 400 client error response should be cached (deterministic error)."""
        from starlette.requests import Request

        from app.middleware.idempotency import IdempotencyMiddleware

        middleware = IdempotencyMiddleware(app=AsyncMock())

        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=None)
        mock_redis.set = AsyncMock(return_value=True)

        request = Request(_make_request_scope("test-key-400"))

        async def call_next(req):
            return _make_streaming_response({"detail": "Bad Request"}, 400)

        with patch(f"{_IDEM}.get_redis", return_value=mock_redis):
            response = await middleware.dispatch(request, call_next)

        assert response.status_code == 400
        # Should have two set calls: processing marker + cache
        assert mock_redis.set.await_count == 2
        cache_call = mock_redis.set.call_args_list[1]
        cached_data = json.loads(cache_call.args[1])
        assert cached_data["status_code"] == 400

    @pytest.mark.asyncio
    async def test_201_response_is_cached(self):
        """A 201 Created response should be cached."""
        from starlette.requests import Request

        from app.middleware.idempotency import IdempotencyMiddleware

        middleware = IdempotencyMiddleware(app=AsyncMock())

        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=None)
        mock_redis.set = AsyncMock(return_value=True)

        request = Request(_make_request_scope("test-key-201"))

        async def call_next(req):
            return _make_streaming_response({"id": "new"}, 201)

        with patch(f"{_IDEM}.get_redis", return_value=mock_redis):
            response = await middleware.dispatch(request, call_next)

        assert response.status_code == 201
        assert mock_redis.set.await_count == 2

    @pytest.mark.asyncio
    async def test_422_response_is_cached(self):
        """A 422 Unprocessable Entity response should be cached."""
        from starlette.requests import Request

        from app.middleware.idempotency import IdempotencyMiddleware

        middleware = IdempotencyMiddleware(app=AsyncMock())

        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=None)
        mock_redis.set = AsyncMock(return_value=True)

        request = Request(_make_request_scope("test-key-422"))

        async def call_next(req):
            return _make_streaming_response({"detail": "Validation Error"}, 422)

        with patch(f"{_IDEM}.get_redis", return_value=mock_redis):
            response = await middleware.dispatch(request, call_next)

        assert response.status_code == 422
        assert mock_redis.set.await_count == 2
