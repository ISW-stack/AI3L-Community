"""Tests for audit findings M-39, M-40, M-41, L-48, L-49."""

import asyncio
import json
from unittest.mock import AsyncMock, patch

import pytest


class TestM39BeatScheduleExpires:
    """M-39: Every Beat task must have an 'expires' option to prevent overlap."""

    def test_all_beat_tasks_have_expires(self) -> None:
        from app.celery_app import celery

        schedule = celery.conf.beat_schedule
        assert len(schedule) > 0, "beat_schedule should not be empty"

        for name, entry in schedule.items():
            opts = entry.get("options", {})
            assert "expires" in opts, f"Beat task '{name}' missing 'expires' option"
            assert opts["expires"] > 0, f"Beat task '{name}' has non-positive expires"

    def test_expires_matches_schedule_interval(self) -> None:
        """expires should equal the schedule interval so tasks don't pile up."""
        from app.celery_app import celery

        for name, entry in celery.conf.beat_schedule.items():
            schedule_seconds = entry["schedule"]
            expires = entry["options"]["expires"]
            assert (
                expires == schedule_seconds
            ), f"Beat task '{name}': expires ({expires}) != schedule ({schedule_seconds})"


class TestM40RejectOnWorkerLost:
    """M-40: task_reject_on_worker_lost must be True alongside task_acks_late."""

    def test_reject_on_worker_lost_enabled(self) -> None:
        from app.celery_app import celery

        assert celery.conf.task_acks_late is True
        assert celery.conf.task_reject_on_worker_lost is True


class TestM41RunAsyncTimeout:
    """M-41: run_async() must accept a timeout to prevent deadlocked workers."""

    def test_run_async_has_timeout_param(self) -> None:
        import inspect

        from app.tasks.async_runner import run_async

        sig = inspect.signature(run_async)
        assert "timeout" in sig.parameters
        # Default should be 600 (matching task_time_limit)
        assert sig.parameters["timeout"].default == 600

    def test_run_async_timeout_raises(self) -> None:
        """A coroutine exceeding the timeout should raise TimeoutError."""
        from concurrent.futures import TimeoutError as FuturesTimeoutError

        from app.tasks.async_runner import run_async

        async def slow_coro() -> str:
            await asyncio.sleep(10)
            return "done"

        with pytest.raises(FuturesTimeoutError):
            run_async(slow_coro(), timeout=0.05)

    def test_run_async_completes_within_timeout(self) -> None:
        from app.tasks.async_runner import run_async

        async def fast_coro() -> str:
            return "ok"

        result = run_async(fast_coro(), timeout=5)
        assert result == "ok"


class TestL49RedactKwargs:
    """L-49: Sensitive fields must be redacted before persisting to Redis."""

    def test_redact_sensitive_keys(self) -> None:
        from app.core.event_bus import _redact_kwargs

        kwargs = {
            "user_id": "abc-123",
            "content": "secret message",
            "message": "hello world",
            "body": "<p>content</p>",
            "password": "hunter2",
            "token": "jwt-token",
            "action_type": "DM_SENT",
        }
        result = _redact_kwargs(kwargs)

        assert result["user_id"] == "abc-123"
        assert result["action_type"] == "DM_SENT"
        assert result["content"] == "[REDACTED]"
        assert result["message"] == "[REDACTED]"
        assert result["body"] == "[REDACTED]"
        assert result["password"] == "[REDACTED]"
        assert result["token"] == "[REDACTED]"

    def test_redact_nested_dict(self) -> None:
        from app.core.event_bus import _redact_kwargs

        kwargs = {
            "metadata": {
                "content": "nested secret",
                "safe_field": 42,
            },
            "sig_id": "sig-1",
        }
        result = _redact_kwargs(kwargs)

        assert result["sig_id"] == "sig-1"
        assert result["metadata"]["content"] == "[REDACTED]"
        assert result["metadata"]["safe_field"] == 42

    def test_redact_preserves_non_sensitive(self) -> None:
        from app.core.event_bus import _redact_kwargs

        kwargs = {"user_id": "u1", "post_id": "p1", "count": 5}
        result = _redact_kwargs(kwargs)
        assert result == kwargs

    def test_redact_empty_dict(self) -> None:
        from app.core.event_bus import _redact_kwargs

        assert _redact_kwargs({}) == {}

    @pytest.mark.asyncio
    async def test_persist_failed_event_uses_redacted_kwargs(self) -> None:
        """Ensure _persist_failed_event redacts sensitive fields in Redis entry."""
        from app.core.event_bus import _persist_failed_event

        mock_redis = AsyncMock()
        mock_redis.lpush = AsyncMock(return_value=1)
        mock_redis.ltrim = AsyncMock(return_value=True)
        mock_redis.expire = AsyncMock(return_value=True)

        with patch("app.core.redis.get_redis", return_value=mock_redis):
            await _persist_failed_event(
                "dm.message_sent",
                "_on_dm_message_sent",
                {"sender_id": "u1", "content": "super secret", "token": "jwt"},
                retry_count=0,
            )

        # Verify lpush was called
        mock_redis.lpush.assert_called_once()
        call_args = mock_redis.lpush.call_args
        raw_entry = call_args[0][1]
        entry = json.loads(raw_entry)

        assert entry["kwargs"]["sender_id"] == "u1"
        assert entry["kwargs"]["content"] == "[REDACTED]"
        assert entry["kwargs"]["token"] == "[REDACTED]"


class TestL48EventIdDedup:
    """L-48: Persisted events must have a unique event_id for dedup on retry."""

    @pytest.mark.asyncio
    async def test_persist_adds_event_id(self) -> None:
        from app.core.event_bus import _persist_failed_event

        mock_redis = AsyncMock()
        mock_redis.lpush = AsyncMock(return_value=1)
        mock_redis.ltrim = AsyncMock(return_value=True)
        mock_redis.expire = AsyncMock(return_value=True)

        with patch("app.core.redis.get_redis", return_value=mock_redis):
            await _persist_failed_event("test.event", "handler", {"key": "val"}, retry_count=0)

        raw_entry = mock_redis.lpush.call_args[0][1]
        entry = json.loads(raw_entry)
        assert "event_id" in entry
        # Should be a valid UUID string
        import uuid

        uuid.UUID(entry["event_id"])  # Raises if invalid

    @pytest.mark.asyncio
    async def test_persist_generates_unique_ids(self) -> None:
        from app.core.event_bus import _persist_failed_event

        mock_redis = AsyncMock()
        mock_redis.lpush = AsyncMock(return_value=1)
        mock_redis.ltrim = AsyncMock(return_value=True)
        mock_redis.expire = AsyncMock(return_value=True)

        ids = []
        with patch("app.core.redis.get_redis", return_value=mock_redis):
            for _ in range(3):
                await _persist_failed_event("test.event", "handler", {"key": "val"}, retry_count=0)

        for call in mock_redis.lpush.call_args_list:
            entry = json.loads(call[0][1])
            ids.append(entry["event_id"])

        assert len(set(ids)) == 3, "Each persisted event should have a unique event_id"
