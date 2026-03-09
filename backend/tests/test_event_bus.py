"""Comprehensive tests for app.core.event_bus module."""

import json
from unittest.mock import AsyncMock, patch

import pytest

from app.core import event_bus
from app.core.event_bus import MAX_RETRIES, _persist_failed_event, clear, emit, on


@pytest.fixture(autouse=True)
def _clean_handlers():
    """Ensure a clean handler registry for every test."""
    clear()
    yield
    clear()


# ---------------------------------------------------------------------------
# Handler registration
# ---------------------------------------------------------------------------


class TestRegistration:
    def test_register_single_handler(self):
        async def handler(**kw):
            pass

        on("test_event", handler)
        assert handler in event_bus._handlers["test_event"]

    def test_register_multiple_handlers_same_event(self):
        async def h1(**kw):
            pass

        async def h2(**kw):
            pass

        on("test_event", h1)
        on("test_event", h2)
        assert event_bus._handlers["test_event"] == [h1, h2]

    def test_register_handlers_different_events(self):
        async def h1(**kw):
            pass

        async def h2(**kw):
            pass

        on("event_a", h1)
        on("event_b", h2)
        assert event_bus._handlers["event_a"] == [h1]
        assert event_bus._handlers["event_b"] == [h2]

    def test_clear_removes_all_handlers(self):
        on("a", AsyncMock())
        on("b", AsyncMock())
        clear()
        assert len(event_bus._handlers) == 0

    def test_register_same_handler_twice(self):
        """Registering the same handler twice adds it twice (by design)."""
        handler = AsyncMock()
        on("evt", handler)
        on("evt", handler)
        assert len(event_bus._handlers["evt"]) == 2


# ---------------------------------------------------------------------------
# Event emission - happy path
# ---------------------------------------------------------------------------


class TestEmitHappyPath:
    @pytest.mark.asyncio
    async def test_emit_calls_handler_with_kwargs(self):
        handler = AsyncMock()
        on("user.created", handler)

        await emit("user.created", user_id="abc", role="MEMBER")

        handler.assert_awaited_once_with(user_id="abc", role="MEMBER")

    @pytest.mark.asyncio
    async def test_emit_calls_all_handlers_for_event(self):
        h1 = AsyncMock()
        h2 = AsyncMock()
        on("post.published", h1)
        on("post.published", h2)

        await emit("post.published", post_id=1)

        h1.assert_awaited_once_with(post_id=1)
        h2.assert_awaited_once_with(post_id=1)

    @pytest.mark.asyncio
    async def test_emit_no_handlers_does_nothing(self):
        """Emitting an event with no registered handlers should not raise."""
        await emit("nonexistent.event", data="hello")

    @pytest.mark.asyncio
    async def test_emit_no_kwargs(self):
        handler = AsyncMock()
        on("ping", handler)

        await emit("ping")

        handler.assert_awaited_once_with()

    @pytest.mark.asyncio
    async def test_emit_does_not_trigger_other_events(self):
        h_target = AsyncMock()
        h_other = AsyncMock()
        on("target", h_target)
        on("other", h_other)

        await emit("target", x=1)

        h_target.assert_awaited_once()
        h_other.assert_not_awaited()


# ---------------------------------------------------------------------------
# Retry behaviour
# ---------------------------------------------------------------------------


class TestRetryBehaviour:
    @pytest.mark.asyncio
    async def test_retry_succeeds_on_second_attempt(self):
        """Handler fails once then succeeds - no Redis persistence."""
        handler = AsyncMock(side_effect=[Exception("boom"), None])
        on("evt", handler)

        with patch("app.core.event_bus.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            with patch(
                "app.core.event_bus._persist_failed_event", new_callable=AsyncMock
            ) as mock_persist:
                await emit("evt", key="val")

        assert handler.await_count == 2
        mock_sleep.assert_awaited_once_with(event_bus.RETRY_DELAY)
        mock_persist.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_retry_succeeds_on_third_attempt(self):
        """Handler fails twice then succeeds on the last allowed attempt."""
        handler = AsyncMock(side_effect=[Exception("1"), Exception("2"), None])
        on("evt", handler)

        with patch("app.core.event_bus.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            with patch(
                "app.core.event_bus._persist_failed_event", new_callable=AsyncMock
            ) as mock_persist:
                await emit("evt")

        # 1 initial + MAX_RETRIES(2) = 3 total attempts
        assert handler.await_count == 3
        assert mock_sleep.await_count == MAX_RETRIES
        mock_persist.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_all_retries_exhausted_persists_to_redis(self):
        """When all attempts fail, the event is persisted to Redis."""
        handler = AsyncMock(side_effect=Exception("always fails"))
        on("evt", handler)

        with patch("app.core.event_bus.asyncio.sleep", new_callable=AsyncMock):
            with patch(
                "app.core.event_bus._persist_failed_event", new_callable=AsyncMock
            ) as mock_persist:
                await emit("evt", x=42)

        # 1 initial + MAX_RETRIES retries = MAX_RETRIES + 1 total
        assert handler.await_count == MAX_RETRIES + 1
        mock_persist.assert_awaited_once()
        call_args = mock_persist.call_args
        assert call_args[0][0] == "evt"  # event name
        assert call_args[1] == {"retry_count": 0}

    @pytest.mark.asyncio
    async def test_retry_delay_uses_configured_value(self):
        handler = AsyncMock(side_effect=[Exception("x"), None])
        on("evt", handler)

        with patch("app.core.event_bus.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            with patch("app.core.event_bus._persist_failed_event", new_callable=AsyncMock):
                await emit("evt")

        mock_sleep.assert_awaited_with(event_bus.RETRY_DELAY)

    @pytest.mark.asyncio
    async def test_one_handler_fails_other_still_runs(self):
        """A failing handler does not prevent subsequent handlers from running."""
        failing = AsyncMock(side_effect=Exception("broken"))
        succeeding = AsyncMock()
        on("evt", failing)
        on("evt", succeeding)

        with patch("app.core.event_bus.asyncio.sleep", new_callable=AsyncMock):
            with patch("app.core.event_bus._persist_failed_event", new_callable=AsyncMock):
                await emit("evt", data="hello")

        succeeding.assert_awaited_once_with(data="hello")


# ---------------------------------------------------------------------------
# _persist_failed_event
# ---------------------------------------------------------------------------


class TestPersistFailedEvent:
    @pytest.mark.asyncio
    async def test_persist_pushes_to_redis(self, mock_redis):
        with patch("app.core.redis.get_redis", return_value=mock_redis):
            await _persist_failed_event(
                "user.deleted", "handle_delete", {"user_id": "abc"}, retry_count=0
            )

        mock_redis.lpush.assert_awaited_once()
        key, value = mock_redis.lpush.call_args[0]
        assert key == "event_bus:failed"

        payload = json.loads(value)
        assert payload["event"] == "user.deleted"
        assert payload["handler"] == "handle_delete"
        assert payload["kwargs"] == {"user_id": "abc"}
        assert payload["retry_count"] == 0

    @pytest.mark.asyncio
    async def test_persist_trims_list_to_1000(self, mock_redis):
        with patch("app.core.redis.get_redis", return_value=mock_redis):
            await _persist_failed_event("e", "h", {}, retry_count=0)

        mock_redis.ltrim.assert_awaited_once_with("event_bus:failed", 0, 999)

    @pytest.mark.asyncio
    async def test_persist_sets_24h_ttl(self, mock_redis):
        with patch("app.core.redis.get_redis", return_value=mock_redis):
            await _persist_failed_event("e", "h", {}, retry_count=0)

        mock_redis.expire.assert_awaited_once_with("event_bus:failed", 86400)

    @pytest.mark.asyncio
    async def test_persist_handles_redis_failure_gracefully(self):
        """If Redis is unavailable, _persist_failed_event does not raise."""
        bad_redis = AsyncMock()
        bad_redis.lpush = AsyncMock(side_effect=ConnectionError("Redis down"))

        with patch("app.core.redis.get_redis", return_value=bad_redis):
            await _persist_failed_event("e", "h", {"a": 1}, retry_count=0)

    @pytest.mark.asyncio
    async def test_persist_handles_get_redis_import_error(self):
        """If get_redis itself raises, _persist_failed_event suppresses it."""
        with patch("app.core.redis.get_redis", side_effect=RuntimeError("not initialised")):
            await _persist_failed_event("e", "h", {}, retry_count=0)

    @pytest.mark.asyncio
    async def test_persist_serialises_non_json_values(self, mock_redis):
        """kwargs with non-JSON-serialisable values use default=str."""
        from uuid import UUID

        uid = UUID("12345678-1234-5678-1234-567812345678")

        with patch("app.core.redis.get_redis", return_value=mock_redis):
            await _persist_failed_event("e", "h", {"id": uid}, retry_count=0)

        _, value = mock_redis.lpush.call_args[0]
        payload = json.loads(value)
        assert payload["kwargs"]["id"] == str(uid)


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    @pytest.mark.asyncio
    async def test_emit_empty_event_name(self):
        handler = AsyncMock()
        on("", handler)
        await emit("")
        handler.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_handler_name_uses_dunder_name(self):
        """Handler name extraction uses __name__ for named functions."""

        async def my_handler(**kw):
            raise Exception("fail")

        on("evt", my_handler)

        with patch("app.core.event_bus.asyncio.sleep", new_callable=AsyncMock):
            with patch(
                "app.core.event_bus._persist_failed_event", new_callable=AsyncMock
            ) as mock_persist:
                await emit("evt")

        handler_name_arg = mock_persist.call_args[0][1]
        assert handler_name_arg == "my_handler"

    @pytest.mark.asyncio
    async def test_handler_name_falls_back_to_repr(self):
        """Lambdas or objects without __name__ fall back to repr()."""

        class CallableHandler:
            async def __call__(self, **kw):
                raise Exception("fail")

            def __repr__(self):
                return "<CallableHandler>"

        handler = CallableHandler()
        assert not hasattr(handler, "__name__")
        on("evt", handler)

        with patch("app.core.event_bus.asyncio.sleep", new_callable=AsyncMock):
            with patch(
                "app.core.event_bus._persist_failed_event", new_callable=AsyncMock
            ) as mock_persist:
                await emit("evt")

        handler_name_arg = mock_persist.call_args[0][1]
        assert handler_name_arg == "<CallableHandler>"

    @pytest.mark.asyncio
    async def test_max_retries_constant(self):
        """Verify MAX_RETRIES is 2 as documented."""
        assert MAX_RETRIES == 2

    @pytest.mark.asyncio
    async def test_emit_with_many_kwargs(self):
        handler = AsyncMock()
        on("complex", handler)

        kwargs = {f"key_{i}": i for i in range(20)}
        await emit("complex", **kwargs)

        handler.assert_awaited_once_with(**kwargs)

    @pytest.mark.asyncio
    async def test_clear_between_emits(self):
        """After clear(), previously registered handlers are not called."""
        handler = AsyncMock()
        on("evt", handler)
        clear()

        await emit("evt")

        handler.assert_not_awaited()
