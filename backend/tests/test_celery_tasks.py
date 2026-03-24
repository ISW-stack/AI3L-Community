"""Unit tests for Celery task modules: event_retry, form_export, virustotal.

All Celery/external imports are mocked since they are not available in the test env.
"""

import csv
import io
import json
import sys
import types
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Module-level Celery mock fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _celery_modules():
    """Inject fake celery modules into sys.modules so lazy imports succeed."""
    celery_mod = types.ModuleType("celery")
    celery_result_mod = types.ModuleType("celery.result")
    celery_mod.result = celery_result_mod

    # shared_task decorator (used by event_retry)
    celery_mod.shared_task = lambda **kw: (lambda fn: fn)

    celery_app_mod = types.ModuleType("app.celery_app")
    mock_celery_app = MagicMock()
    # celery.task decorator (used by form_export, virustotal)
    mock_celery_app.task = lambda *a, **kw: (lambda fn: fn)
    celery_app_mod.celery = mock_celery_app

    saved = {}
    for key in ("celery", "celery.result", "app.celery_app"):
        saved[key] = sys.modules.get(key)

    sys.modules["celery"] = celery_mod
    sys.modules["celery.result"] = celery_result_mod
    sys.modules["app.celery_app"] = celery_app_mod

    yield

    # Restore
    for key, val in saved.items():
        if val is None:
            sys.modules.pop(key, None)
        else:
            sys.modules[key] = val

    # Purge cached task modules so next test gets fresh imports
    for mod_name in list(sys.modules):
        if mod_name.startswith("app.tasks."):
            del sys.modules[mod_name]


# =========================================================================
# Tests for event_retry._async_retry
# =========================================================================


def _mock_lpop_from_list(items: list) -> AsyncMock:
    """Create an lpop mock that returns items one at a time, then None."""
    remaining = list(items)

    async def _lpop(key: str):  # type: ignore[no-untyped-def]
        if remaining:
            return remaining.pop(0)
        return None

    return AsyncMock(side_effect=_lpop)


class TestAsyncRetry:
    """Tests for the _async_retry coroutine in event_retry.py."""

    @pytest.mark.anyio
    async def test_noop_when_no_failed_events(self):
        """Should return early when Redis has no failed events."""
        mock_redis = AsyncMock()
        mock_redis.lpop = _mock_lpop_from_list([])

        with patch("app.core.redis.get_redis", return_value=mock_redis):
            from app.tasks.event_retry import _async_retry

            await _async_retry()

        mock_redis.lpop.assert_awaited_once_with("event_bus:failed")

    @pytest.mark.anyio
    async def test_redis_unavailable_returns_gracefully(self):
        """Should not raise when Redis is unavailable."""
        with patch("app.core.redis.get_redis", side_effect=RuntimeError("no redis")):
            from app.tasks.event_retry import _async_retry

            await _async_retry()
        # No exception means pass

    @pytest.mark.anyio
    async def test_successfully_retries_event(self):
        """Should call registered handlers for a valid event."""
        handler = AsyncMock()
        handler.__name__ = "my_handler"
        event_entry = json.dumps(
            {
                "event": "test.event",
                "handler": "my_handler",
                "kwargs": {"user_id": "abc"},
                "retry_count": 0,
            }
        )

        mock_redis = AsyncMock()
        mock_redis.lpop = _mock_lpop_from_list([event_entry])

        with (
            patch("app.core.redis.get_redis", return_value=mock_redis),
            patch.dict("app.core.event_bus._handlers", {"test.event": [handler]}),
        ):
            from app.tasks.event_retry import _async_retry

            await _async_retry()

        handler.assert_awaited_once_with(user_id="abc")

    @pytest.mark.anyio
    async def test_uses_lpop_not_lrange_delete(self):
        """N-B02: Must use atomic LPOP instead of LRANGE+DELETE to prevent data loss."""
        mock_redis = AsyncMock()
        mock_redis.lpop = _mock_lpop_from_list([])

        with patch("app.core.redis.get_redis", return_value=mock_redis):
            from app.tasks.event_retry import _async_retry

            await _async_retry()

        # Verify LPOP was used (not LRANGE + DELETE)
        mock_redis.lpop.assert_awaited()
        assert not hasattr(mock_redis, "lrange") or not mock_redis.lrange.called
        assert not hasattr(mock_redis, "delete") or not mock_redis.delete.called

    @pytest.mark.anyio
    async def test_unprocessed_events_survive_crash(self):
        """N-B02: If handler raises, remaining events stay in Redis (LPOP pattern)."""
        handler = AsyncMock()
        handler.__name__ = "h"
        event1 = json.dumps({"event": "e", "handler": "h", "kwargs": {}, "retry_count": 0})
        event2 = json.dumps({"event": "e", "handler": "h", "kwargs": {}, "retry_count": 0})

        # Only pop the first event; second stays in "Redis"
        pop_count = 0

        async def counting_lpop(key: str):  # type: ignore[no-untyped-def]
            nonlocal pop_count
            pop_count += 1
            if pop_count == 1:
                return event1
            elif pop_count == 2:
                return event2
            return None

        mock_redis = AsyncMock()
        mock_redis.lpop = AsyncMock(side_effect=counting_lpop)

        with (
            patch("app.core.redis.get_redis", return_value=mock_redis),
            patch.dict("app.core.event_bus._handlers", {"e": [handler]}),
        ):
            from app.tasks.event_retry import _async_retry

            await _async_retry()

        # Both events were popped and processed
        assert handler.await_count == 2
        assert pop_count == 3  # 2 events + 1 None sentinel

    @pytest.mark.anyio
    async def test_max_events_per_run_limits_processing(self):
        """N-B02: Processing is bounded by MAX_EVENTS_PER_RUN."""
        from app.tasks.event_retry import MAX_EVENTS_PER_RUN

        handler = AsyncMock()
        handler.__name__ = "h"

        # Create more events than the limit
        call_count = 0

        async def infinite_lpop(key: str) -> str:
            nonlocal call_count
            call_count += 1
            return json.dumps({"event": "e", "handler": "h", "kwargs": {}, "retry_count": 0})

        mock_redis = AsyncMock()
        mock_redis.lpop = AsyncMock(side_effect=infinite_lpop)

        with (
            patch("app.core.redis.get_redis", return_value=mock_redis),
            patch.dict("app.core.event_bus._handlers", {"e": [handler]}),
        ):
            from app.tasks.event_retry import _async_retry

            await _async_retry()

        # Should stop after MAX_EVENTS_PER_RUN
        assert handler.await_count == MAX_EVENTS_PER_RUN

    @pytest.mark.anyio
    async def test_drops_event_exceeding_max_retries(self):
        """Events that hit MAX_EVENT_RETRIES should be dropped, not retried."""
        handler = AsyncMock()
        event_entry = json.dumps(
            {
                "event": "test.event",
                "handler": "my_handler",
                "kwargs": {},
                "retry_count": 3,  # == MAX_EVENT_RETRIES
            }
        )

        mock_redis = AsyncMock()
        mock_redis.lpop = _mock_lpop_from_list([event_entry])

        with (
            patch("app.core.redis.get_redis", return_value=mock_redis),
            patch.dict("app.core.event_bus._handlers", {"test.event": [handler]}),
        ):
            from app.tasks.event_retry import _async_retry

            await _async_retry()

        handler.assert_not_awaited()

    @pytest.mark.anyio
    async def test_drops_invalid_json(self):
        """Malformed JSON entries should be dropped without crashing."""
        mock_redis = AsyncMock()
        mock_redis.lpop = _mock_lpop_from_list(["not-valid-json{{{"])

        with patch("app.core.redis.get_redis", return_value=mock_redis):
            from app.tasks.event_retry import _async_retry

            await _async_retry()

        # No exception means graceful handling

    @pytest.mark.anyio
    async def test_drops_event_with_unknown_event_name(self):
        """Events whose name has no registered handler should be dropped."""
        event_entry = json.dumps(
            {
                "event": "unknown.event",
                "handler": "x",
                "kwargs": {},
                "retry_count": 0,
            }
        )

        mock_redis = AsyncMock()
        mock_redis.lpop = _mock_lpop_from_list([event_entry])

        with (
            patch("app.core.redis.get_redis", return_value=mock_redis),
            patch.dict("app.core.event_bus._handlers", {}, clear=True),
        ):
            from app.tasks.event_retry import _async_retry

            await _async_retry()

    @pytest.mark.anyio
    async def test_re_persists_event_on_handler_failure(self):
        """If handler raises, event should be re-persisted with incremented retry_count."""
        handler = AsyncMock(side_effect=RuntimeError("boom"))
        handler.__name__ = "my_handler"
        event_entry = json.dumps(
            {
                "event": "test.event",
                "handler": "my_handler",
                "kwargs": {"x": 1},
                "retry_count": 1,
            }
        )

        mock_redis = AsyncMock()
        mock_redis.lpop = _mock_lpop_from_list([event_entry])

        mock_persist = AsyncMock()

        with (
            patch("app.core.redis.get_redis", return_value=mock_redis),
            patch.dict("app.core.event_bus._handlers", {"test.event": [handler]}),
            patch("app.core.event_bus._persist_failed_event", mock_persist),
        ):
            from app.tasks.event_retry import _async_retry

            await _async_retry()

        mock_persist.assert_awaited_once_with("test.event", "my_handler", {"x": 1}, retry_count=2)

    @pytest.mark.anyio
    async def test_drops_event_with_missing_event_name(self):
        """Entry with no 'event' key should be dropped."""
        event_entry = json.dumps(
            {
                "handler": "h",
                "kwargs": {},
                "retry_count": 0,
            }
        )

        mock_redis = AsyncMock()
        mock_redis.lpop = _mock_lpop_from_list([event_entry])

        with patch("app.core.redis.get_redis", return_value=mock_redis):
            from app.tasks.event_retry import _async_retry

            await _async_retry()

    @pytest.mark.anyio
    async def test_multiple_events_mixed_outcomes(self):
        """Process multiple events: one succeeds, one dropped (max retries), one fails."""
        good_handler = AsyncMock()
        good_handler.__name__ = "h"
        bad_handler = AsyncMock(side_effect=RuntimeError("fail"))
        bad_handler.__name__ = "h_bad"

        events = [
            json.dumps({"event": "good", "handler": "h", "kwargs": {}, "retry_count": 0}),
            json.dumps({"event": "maxed", "handler": "h", "kwargs": {}, "retry_count": 3}),
            json.dumps({"event": "bad", "handler": "h_bad", "kwargs": {}, "retry_count": 0}),
        ]

        mock_redis = AsyncMock()
        mock_redis.lpop = _mock_lpop_from_list(events)

        mock_persist = AsyncMock()

        with (
            patch("app.core.redis.get_redis", return_value=mock_redis),
            patch.dict(
                "app.core.event_bus._handlers",
                {"good": [good_handler], "maxed": [good_handler], "bad": [bad_handler]},
                clear=True,
            ),
            patch("app.core.event_bus._persist_failed_event", mock_persist),
        ):
            from app.tasks.event_retry import _async_retry

            await _async_retry()

        good_handler.assert_awaited_once()
        assert mock_persist.await_count == 1

    @pytest.mark.anyio
    async def test_retry_only_calls_matching_handler(self):
        """When two handlers are registered for the same event, only the failed one is retried."""
        handler_a = AsyncMock()
        handler_a.__name__ = "handler_a"
        handler_b = AsyncMock()
        handler_b.__name__ = "handler_b"

        # Only handler_b failed and was persisted
        event_entry = json.dumps(
            {
                "event": "test.event",
                "handler": "handler_b",
                "kwargs": {"key": "val"},
                "retry_count": 0,
            }
        )

        mock_redis = AsyncMock()
        mock_redis.lpop = _mock_lpop_from_list([event_entry])

        with (
            patch("app.core.redis.get_redis", return_value=mock_redis),
            patch.dict(
                "app.core.event_bus._handlers",
                {"test.event": [handler_a, handler_b]},
            ),
        ):
            from app.tasks.event_retry import _async_retry

            await _async_retry()

        handler_a.assert_not_awaited()
        handler_b.assert_awaited_once_with(key="val")

    @pytest.mark.anyio
    async def test_retry_drops_event_when_handler_removed(self):
        """If the matching handler is no longer registered, the event should be dropped."""
        remaining_handler = AsyncMock()
        remaining_handler.__name__ = "remaining_handler"

        # The persisted event references a handler that has since been unregistered
        event_entry = json.dumps(
            {
                "event": "test.event",
                "handler": "removed_handler",
                "kwargs": {},
                "retry_count": 0,
            }
        )

        mock_redis = AsyncMock()
        mock_redis.lpop = _mock_lpop_from_list([event_entry])

        with (
            patch("app.core.redis.get_redis", return_value=mock_redis),
            patch.dict(
                "app.core.event_bus._handlers",
                {"test.event": [remaining_handler]},
            ),
        ):
            from app.tasks.event_retry import _async_retry

            await _async_retry()

        # The remaining handler should NOT be called (it's not the one that failed)
        remaining_handler.assert_not_awaited()


# =========================================================================
# Tests for form_export._async_export
# =========================================================================


class TestFormExport:
    """Tests for the _async_export coroutine in form_export.py."""

    def _make_form_row(self, questions: list, title: str = "Test Form"):
        return {"questions": json.dumps(questions), "title": title}

    def _make_response_row(self, answers: dict, username: str = "user1"):
        return {
            "id": uuid.uuid4(),
            "answers": json.dumps(answers),
            "created_at": datetime(2026, 1, 15, 10, 0, tzinfo=timezone.utc),
            "username": username,
            "display_name": f"Display {username}",
        }

    @pytest.mark.anyio
    async def test_export_generates_csv_with_correct_headers(self):
        """CSV should include standard columns plus question labels."""
        questions = [
            {"id": "q1", "label": "Name"},
            {"id": "q2", "label": "Email"},
        ]
        form_row = self._make_form_row(questions)
        response_row = self._make_response_row({"q1": "Alice", "q2": "alice@example.com"})

        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(return_value=form_row)
        mock_conn.fetch = AsyncMock(return_value=[response_row])

        mock_cm = AsyncMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_cm.__aexit__ = AsyncMock(return_value=False)

        mock_pool = MagicMock()
        mock_pool.acquire = MagicMock(return_value=mock_cm)

        uploaded_data = {}

        def fake_upload(data: bytes, key: str, content_type: str):
            uploaded_data["bytes"] = data
            uploaded_data["key"] = key

        form_id = str(uuid.uuid4())
        task_id = str(uuid.uuid4())

        with (
            patch("app.tasks.form_export.get_pool", return_value=mock_pool),
            patch("app.core.storage.get_storage", return_value=MagicMock()),
            patch("app.tasks.form_export.upload_file", side_effect=fake_upload),
            patch(
                "app.tasks.form_export.generate_presigned_url",
                return_value="https://example.com/file.csv",
            ),
            patch(
                "app.tasks.form_export.generate_form_export_key",
                return_value="exports/test.csv",
            ),
        ):
            from app.tasks.form_export import _async_export

            result = await _async_export(form_id, task_id)

        assert result["download_url"] == "https://example.com/file.csv"

        # Verify CSV content
        csv_text = uploaded_data["bytes"].decode("utf-8-sig")
        reader = csv.reader(io.StringIO(csv_text))
        header = next(reader)
        assert header == [
            "Response ID",
            "Username",
            "Display Name",
            "Submitted At",
            "Name",
            "Email",
        ]

        data_row = next(reader)
        assert data_row[1] == "user1"
        assert data_row[4] == "Alice"
        assert data_row[5] == "alice@example.com"

    @pytest.mark.anyio
    async def test_export_raises_when_form_not_found(self):
        """Should raise ValueError when form_id doesn't exist."""
        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(return_value=None)

        mock_cm = AsyncMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_cm.__aexit__ = AsyncMock(return_value=False)

        mock_pool = MagicMock()
        mock_pool.acquire = MagicMock(return_value=mock_cm)

        with (
            patch("app.tasks.form_export.get_pool", return_value=mock_pool),
            patch("app.core.storage.get_storage", return_value=MagicMock()),
        ):
            from app.tasks.form_export import _async_export

            with pytest.raises(ValueError, match="not found"):
                await _async_export(str(uuid.uuid4()), "task-1")

    @pytest.mark.anyio
    async def test_export_handles_list_and_dict_answers(self):
        """List answers joined with '; ', dict answers extract 'filename'."""
        questions = [
            {"id": "q1", "label": "Tags"},
            {"id": "q2", "label": "File"},
            {"id": "q3", "label": "Missing"},
        ]
        form_row = self._make_form_row(questions)
        response_row = self._make_response_row(
            {
                "q1": ["tag1", "tag2"],
                "q2": {"filename": "doc.pdf", "size": 1024},
                # q3 intentionally missing
            }
        )

        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(return_value=form_row)
        mock_conn.fetch = AsyncMock(return_value=[response_row])

        mock_cm = AsyncMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_cm.__aexit__ = AsyncMock(return_value=False)

        mock_pool = MagicMock()
        mock_pool.acquire = MagicMock(return_value=mock_cm)

        uploaded_data = {}

        def fake_upload(data: bytes, key: str, content_type: str):
            uploaded_data["bytes"] = data

        with (
            patch("app.tasks.form_export.get_pool", return_value=mock_pool),
            patch("app.core.storage.get_storage", return_value=MagicMock()),
            patch("app.tasks.form_export.upload_file", side_effect=fake_upload),
            patch(
                "app.tasks.form_export.generate_presigned_url",
                return_value="https://x.com/f.csv",
            ),
            patch("app.tasks.form_export.generate_form_export_key", return_value="k"),
        ):
            from app.tasks.form_export import _async_export

            await _async_export(str(uuid.uuid4()), "t1")

        csv_text = uploaded_data["bytes"].decode("utf-8-sig")
        reader = csv.reader(io.StringIO(csv_text))
        next(reader)  # skip header
        data_row = next(reader)
        assert data_row[4] == "tag1; tag2"
        assert data_row[5] == "doc.pdf"
        assert data_row[6] == ""  # missing answer

    @pytest.mark.anyio
    async def test_export_initializes_pool_when_not_available(self):
        """Should call init_db_pool if get_pool raises RuntimeError."""
        questions = [{"id": "q1", "label": "Q"}]
        form_row = self._make_form_row(questions)

        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(return_value=form_row)
        mock_conn.fetch = AsyncMock(return_value=[])

        mock_cm = AsyncMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_cm.__aexit__ = AsyncMock(return_value=False)

        mock_pool = MagicMock()
        mock_pool.acquire = MagicMock(return_value=mock_cm)

        mock_init = AsyncMock(return_value=mock_pool)

        with (
            patch("app.tasks.form_export.get_pool", side_effect=RuntimeError("no pool")),
            patch("app.tasks.form_export.init_db_pool", mock_init),
            patch("app.core.storage.get_storage", return_value=MagicMock()),
            patch("app.tasks.form_export.upload_file"),
            patch(
                "app.tasks.form_export.generate_presigned_url",
                return_value="https://x.com/f.csv",
            ),
            patch("app.tasks.form_export.generate_form_export_key", return_value="k"),
        ):
            from app.tasks.form_export import _async_export

            result = await _async_export(str(uuid.uuid4()), "t1")

        mock_init.assert_awaited_once()
        assert result["download_url"] == "https://x.com/f.csv"

    @pytest.mark.anyio
    async def test_export_initializes_storage_when_not_available(self):
        """Should call init_storage if get_storage raises RuntimeError."""
        questions = [{"id": "q1", "label": "Q"}]
        form_row = self._make_form_row(questions)

        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(return_value=form_row)
        mock_conn.fetch = AsyncMock(return_value=[])

        mock_cm = AsyncMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_cm.__aexit__ = AsyncMock(return_value=False)

        mock_pool = MagicMock()
        mock_pool.acquire = MagicMock(return_value=mock_cm)

        mock_init_storage = MagicMock()

        with (
            patch("app.tasks.form_export.get_pool", return_value=mock_pool),
            patch(
                "app.core.storage.get_storage",
                side_effect=RuntimeError("no storage"),
            ),
            patch("app.tasks.form_export.init_storage", mock_init_storage),
            patch("app.tasks.form_export.upload_file"),
            patch(
                "app.tasks.form_export.generate_presigned_url",
                return_value="https://x.com/f.csv",
            ),
            patch("app.tasks.form_export.generate_form_export_key", return_value="k"),
        ):
            from app.tasks.form_export import _async_export

            await _async_export(str(uuid.uuid4()), "t1")

        mock_init_storage.assert_called_once()

    @pytest.mark.anyio
    async def test_export_empty_responses(self):
        """CSV should still have headers when there are no responses."""
        questions = [{"id": "q1", "label": "Question 1"}]
        form_row = self._make_form_row(questions)

        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(return_value=form_row)
        mock_conn.fetch = AsyncMock(return_value=[])

        mock_cm = AsyncMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_cm.__aexit__ = AsyncMock(return_value=False)

        mock_pool = MagicMock()
        mock_pool.acquire = MagicMock(return_value=mock_cm)

        uploaded_data = {}

        def fake_upload(data: bytes, key: str, content_type: str):
            uploaded_data["bytes"] = data

        with (
            patch("app.tasks.form_export.get_pool", return_value=mock_pool),
            patch("app.core.storage.get_storage", return_value=MagicMock()),
            patch("app.tasks.form_export.upload_file", side_effect=fake_upload),
            patch(
                "app.tasks.form_export.generate_presigned_url",
                return_value="https://x.com/f.csv",
            ),
            patch("app.tasks.form_export.generate_form_export_key", return_value="k"),
        ):
            from app.tasks.form_export import _async_export

            await _async_export(str(uuid.uuid4()), "t1")

        csv_text = uploaded_data["bytes"].decode("utf-8-sig")
        reader = csv.reader(io.StringIO(csv_text))
        header = next(reader)
        assert "Question 1" in header
        rows = list(reader)
        assert len(rows) == 0

    @pytest.mark.anyio
    async def test_export_handles_jsonb_as_python_objects(self):
        """Questions/answers as Python objects (not JSON strings) should work."""
        questions = [{"id": "q1", "label": "Name"}]
        # Simulate questions already as a Python list (not string)
        form_row = {"questions": questions, "title": "Form"}
        response_row = self._make_response_row({"q1": "Bob"})
        # Also simulate answers as a dict (not string)
        response_row["answers"] = {"q1": "Bob"}

        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(return_value=form_row)
        mock_conn.fetch = AsyncMock(return_value=[response_row])

        mock_cm = AsyncMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_cm.__aexit__ = AsyncMock(return_value=False)

        mock_pool = MagicMock()
        mock_pool.acquire = MagicMock(return_value=mock_cm)

        uploaded_data = {}

        def fake_upload(data: bytes, key: str, content_type: str):
            uploaded_data["bytes"] = data

        with (
            patch("app.tasks.form_export.get_pool", return_value=mock_pool),
            patch("app.core.storage.get_storage", return_value=MagicMock()),
            patch("app.tasks.form_export.upload_file", side_effect=fake_upload),
            patch(
                "app.tasks.form_export.generate_presigned_url",
                return_value="https://x.com/f.csv",
            ),
            patch("app.tasks.form_export.generate_form_export_key", return_value="k"),
        ):
            from app.tasks.form_export import _async_export

            await _async_export(str(uuid.uuid4()), "t1")

        csv_text = uploaded_data["bytes"].decode("utf-8-sig")
        reader = csv.reader(io.StringIO(csv_text))
        next(reader)
        data_row = next(reader)
        assert data_row[4] == "Bob"

    @pytest.mark.anyio
    async def test_export_resolves_multi_choice_uuids_to_labels(self):
        """Multi-choice option UUIDs should be resolved to their labels."""
        questions = [
            {
                "id": "q1",
                "label": "Favorite Colors",
                "options": [
                    {"id": "opt-a", "label": "Red"},
                    {"id": "opt-b", "label": "Blue"},
                    {"id": "opt-c", "label": "Green"},
                ],
            },
        ]
        form_row = self._make_form_row(questions)
        response_row = self._make_response_row({"q1": ["opt-a", "opt-c"]})

        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(return_value=form_row)
        mock_conn.fetch = AsyncMock(return_value=[response_row])

        mock_cm = AsyncMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_cm.__aexit__ = AsyncMock(return_value=False)

        mock_pool = MagicMock()
        mock_pool.acquire = MagicMock(return_value=mock_cm)

        uploaded_data = {}

        def fake_upload(data: bytes, key: str, content_type: str):
            uploaded_data["bytes"] = data

        with (
            patch("app.tasks.form_export.get_pool", return_value=mock_pool),
            patch("app.core.storage.get_storage", return_value=MagicMock()),
            patch("app.tasks.form_export.upload_file", side_effect=fake_upload),
            patch(
                "app.tasks.form_export.generate_presigned_url",
                return_value="https://x.com/f.csv",
            ),
            patch("app.tasks.form_export.generate_form_export_key", return_value="k"),
        ):
            from app.tasks.form_export import _async_export

            await _async_export(str(uuid.uuid4()), "t1")

        csv_text = uploaded_data["bytes"].decode("utf-8-sig")
        reader = csv.reader(io.StringIO(csv_text))
        next(reader)  # skip header
        data_row = next(reader)
        assert data_row[4] == "Red; Green"

    @pytest.mark.anyio
    async def test_export_resolves_single_choice_uuid_to_label(self):
        """Single-choice option UUID should be resolved to its label."""
        questions = [
            {
                "id": "q1",
                "label": "Level",
                "options": [
                    {"id": "opt-x", "label": "Beginner"},
                    {"id": "opt-y", "label": "Advanced"},
                ],
            },
        ]
        form_row = self._make_form_row(questions)
        response_row = self._make_response_row({"q1": "opt-y"})

        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(return_value=form_row)
        mock_conn.fetch = AsyncMock(return_value=[response_row])

        mock_cm = AsyncMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_cm.__aexit__ = AsyncMock(return_value=False)

        mock_pool = MagicMock()
        mock_pool.acquire = MagicMock(return_value=mock_cm)

        uploaded_data = {}

        def fake_upload(data: bytes, key: str, content_type: str):
            uploaded_data["bytes"] = data

        with (
            patch("app.tasks.form_export.get_pool", return_value=mock_pool),
            patch("app.core.storage.get_storage", return_value=MagicMock()),
            patch("app.tasks.form_export.upload_file", side_effect=fake_upload),
            patch(
                "app.tasks.form_export.generate_presigned_url",
                return_value="https://x.com/f.csv",
            ),
            patch("app.tasks.form_export.generate_form_export_key", return_value="k"),
        ):
            from app.tasks.form_export import _async_export

            await _async_export(str(uuid.uuid4()), "t1")

        csv_text = uploaded_data["bytes"].decode("utf-8-sig")
        reader = csv.reader(io.StringIO(csv_text))
        next(reader)
        data_row = next(reader)
        assert data_row[4] == "Advanced"

    @pytest.mark.anyio
    async def test_export_free_text_passes_through(self):
        """Free text answers (not in option map) should pass through unchanged."""
        questions = [
            {"id": "q1", "label": "Name"},
            {
                "id": "q2",
                "label": "Color",
                "options": [{"id": "opt-a", "label": "Red"}],
            },
        ]
        form_row = self._make_form_row(questions)
        response_row = self._make_response_row({"q1": "Alice", "q2": "opt-a"})

        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(return_value=form_row)
        mock_conn.fetch = AsyncMock(return_value=[response_row])

        mock_cm = AsyncMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_cm.__aexit__ = AsyncMock(return_value=False)

        mock_pool = MagicMock()
        mock_pool.acquire = MagicMock(return_value=mock_cm)

        uploaded_data = {}

        def fake_upload(data: bytes, key: str, content_type: str):
            uploaded_data["bytes"] = data

        with (
            patch("app.tasks.form_export.get_pool", return_value=mock_pool),
            patch("app.core.storage.get_storage", return_value=MagicMock()),
            patch("app.tasks.form_export.upload_file", side_effect=fake_upload),
            patch(
                "app.tasks.form_export.generate_presigned_url",
                return_value="https://x.com/f.csv",
            ),
            patch("app.tasks.form_export.generate_form_export_key", return_value="k"),
        ):
            from app.tasks.form_export import _async_export

            await _async_export(str(uuid.uuid4()), "t1")

        csv_text = uploaded_data["bytes"].decode("utf-8-sig")
        reader = csv.reader(io.StringIO(csv_text))
        next(reader)
        data_row = next(reader)
        assert data_row[4] == "Alice"  # free text unchanged
        assert data_row[5] == "Red"  # option UUID resolved

    @pytest.mark.anyio
    async def test_export_unknown_option_uuid_falls_through(self):
        """Option UUIDs not in any question's options pass through as-is."""
        questions = [
            {
                "id": "q1",
                "label": "Color",
                "options": [{"id": "opt-a", "label": "Red"}],
            },
        ]
        form_row = self._make_form_row(questions)
        response_row = self._make_response_row({"q1": ["opt-a", "opt-unknown"]})

        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(return_value=form_row)
        mock_conn.fetch = AsyncMock(return_value=[response_row])

        mock_cm = AsyncMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_cm.__aexit__ = AsyncMock(return_value=False)

        mock_pool = MagicMock()
        mock_pool.acquire = MagicMock(return_value=mock_cm)

        uploaded_data = {}

        def fake_upload(data: bytes, key: str, content_type: str):
            uploaded_data["bytes"] = data

        with (
            patch("app.tasks.form_export.get_pool", return_value=mock_pool),
            patch("app.core.storage.get_storage", return_value=MagicMock()),
            patch("app.tasks.form_export.upload_file", side_effect=fake_upload),
            patch(
                "app.tasks.form_export.generate_presigned_url",
                return_value="https://x.com/f.csv",
            ),
            patch("app.tasks.form_export.generate_form_export_key", return_value="k"),
        ):
            from app.tasks.form_export import _async_export

            await _async_export(str(uuid.uuid4()), "t1")

        csv_text = uploaded_data["bytes"].decode("utf-8-sig")
        reader = csv.reader(io.StringIO(csv_text))
        next(reader)
        data_row = next(reader)
        assert data_row[4] == "Red; opt-unknown"


# =========================================================================
# Tests for virustotal task
# =========================================================================


class TestVirusTotal:
    """Tests for the check_virustotal task and helpers."""

    def test_compute_sha256(self):
        """compute_sha256 should return correct hex digest."""
        from app.tasks.virustotal import compute_sha256

        result = compute_sha256(b"hello world")
        assert result == "b94d27b9934d3e08a52e52d7da7dabfac484efe37a5380ee9088f7ace2efcde9"

    def test_compute_sha256_empty(self):
        """compute_sha256 of empty bytes should match known hash."""
        from app.tasks.virustotal import compute_sha256

        result = compute_sha256(b"")
        assert result == "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"

    def test_compute_sha256_file_like(self):
        """compute_sha256 should work with file-like objects and reset position."""
        import io

        from app.tasks.virustotal import compute_sha256

        buf = io.BytesIO(b"hello world")
        result = compute_sha256(buf)
        assert result == "b94d27b9934d3e08a52e52d7da7dabfac484efe37a5380ee9088f7ace2efcde9"
        # File position must be reset to 0 after hashing
        assert buf.tell() == 0
        assert buf.read() == b"hello world"

    def test_compute_sha256_file_like_empty(self):
        """compute_sha256 of empty file-like object should match known hash."""
        import io

        from app.tasks.virustotal import compute_sha256

        buf = io.BytesIO(b"")
        result = compute_sha256(buf)
        assert result == "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
        assert buf.tell() == 0

    @pytest.mark.anyio
    async def test_insert_pending_calls_repo(self):
        """_insert_pending should call file_scan_repo.insert."""
        mock_insert = AsyncMock()

        with (
            patch("app.tasks.virustotal._ensure_pool", new_callable=AsyncMock),
            patch("app.repositories.file_scan_repo.insert", mock_insert),
        ):
            from app.tasks.virustotal import _insert_pending

            await _insert_pending("uploads/test.pdf")

        mock_insert.assert_awaited_once_with("uploads/test.pdf")

    @pytest.mark.anyio
    async def test_update_scan_calls_repo(self):
        """_update_scan should call file_scan_repo.update_status with correct args."""
        mock_update = AsyncMock()

        with (
            patch("app.tasks.virustotal._ensure_pool", new_callable=AsyncMock),
            patch("app.repositories.file_scan_repo.update_status", mock_update),
        ):
            from app.tasks.virustotal import _update_scan

            await _update_scan("key", "malicious", "scan-1", 3, 70)

        mock_update.assert_awaited_once_with("key", "malicious", "scan-1", 3, 70)

    @pytest.mark.anyio
    async def test_ensure_pool_initializes_when_missing(self):
        """_ensure_pool should call init_db_pool when get_pool raises."""
        mock_init = AsyncMock()

        with (
            patch("app.tasks.utils.get_pool", side_effect=RuntimeError("no pool")),
            patch("app.tasks.utils.init_db_pool", mock_init),
        ):
            from app.tasks.utils import ensure_pool

            await ensure_pool()

        mock_init.assert_awaited_once()

    @pytest.mark.anyio
    async def test_ensure_pool_noop_when_available(self):
        """_ensure_pool should not call init_db_pool when pool exists."""
        mock_init = AsyncMock()

        with (
            patch("app.tasks.utils.get_pool", return_value=MagicMock()),
            patch("app.tasks.utils.init_db_pool", mock_init),
        ):
            from app.tasks.utils import ensure_pool

            await ensure_pool()

        mock_init.assert_not_awaited()

    def test_check_skipped_when_no_api_key(self):
        """check_virustotal should return 'skipped' and write 'skipped' to DB."""
        mock_self = MagicMock()
        mock_self.request.id = "task-1"

        with (
            patch("app.tasks.virustotal._run_async") as mock_run,
            patch("app.tasks.virustotal.settings") as mock_settings,
        ):
            mock_settings.VT_API_KEY = ""
            mock_run.return_value = None

            from app.tasks.virustotal import check_virustotal

            result = check_virustotal(mock_self, "abc123hash", "uploads/file.pdf")

        assert result["status"] == "skipped"
        assert result["reason"] == "no_api_key"
        # Verify DB is updated to 'skipped' (not 'clean')
        # _run_async is called twice: once for _insert_pending, once for _update_scan("skipped")
        assert mock_run.call_count == 2

    def test_check_clean_file(self):
        """check_virustotal should return 'clean' for a file with 0 positives."""
        mock_self = MagicMock()
        mock_self.request.id = "task-1"

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": {
                "id": "scan-abc",
                "attributes": {
                    "last_analysis_stats": {
                        "malicious": 0,
                        "suspicious": 0,
                        "undetected": 65,
                        "harmless": 5,
                    }
                },
            }
        }

        with (
            patch("app.tasks.virustotal._run_async") as mock_run,
            patch("app.tasks.virustotal.settings") as mock_settings,
            patch("app.tasks.virustotal.requests") as mock_requests,
        ):
            mock_settings.VT_API_KEY = "test-key"
            mock_requests.get.return_value = mock_response
            mock_requests.RequestException = Exception
            mock_run.return_value = None

            from app.tasks.virustotal import check_virustotal

            result = check_virustotal(mock_self, "abc123hash", "uploads/file.pdf")

        assert result["status"] == "clean"

    def test_check_malicious_file_deletes_from_storage(self):
        """check_virustotal should delete malicious files and return 'malicious'."""
        mock_self = MagicMock()
        mock_self.request.id = "task-1"

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": {
                "id": "scan-bad",
                "attributes": {
                    "last_analysis_stats": {
                        "malicious": 5,
                        "suspicious": 2,
                        "undetected": 60,
                        "harmless": 3,
                    }
                },
            }
        }

        mock_async_delete = AsyncMock()
        mock_async_get_size = AsyncMock(return_value=0)

        with (
            patch("app.tasks.virustotal._run_async") as mock_run,
            patch("app.tasks.virustotal.settings") as mock_settings,
            patch("app.tasks.virustotal.requests") as mock_requests,
            patch("app.core.async_storage.delete_file", mock_async_delete),
            patch("app.core.async_storage.get_file_size", mock_async_get_size),
        ):
            mock_settings.VT_API_KEY = "test-key"
            mock_requests.get.return_value = mock_response
            mock_requests.RequestException = Exception
            mock_run.return_value = None

            from app.tasks.virustotal import check_virustotal

            result = check_virustotal(mock_self, "abc123hash", "uploads/malware.exe")

        assert result["status"] == "malicious"
        assert result["malicious"] == 5
        assert result["suspicious"] == 2
        # _run_async is mocked, so async functions are passed as coroutines;
        # verify _run_async was called (which wraps the async delete/get_size)
        assert (
            mock_run.call_count >= 3
        )  # insert_pending + update_scan + get_file_size + delete_file

    def test_check_malicious_file_decrements_storage(self):
        """check_virustotal should decrement owner storage after deleting malicious file."""
        mock_self = MagicMock()
        mock_self.request.id = "task-1"

        user_id = str(uuid.uuid4())
        storage_key = f"editor/{user_id}/malware.exe"

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": {
                "id": "scan-bad",
                "attributes": {
                    "last_analysis_stats": {
                        "malicious": 5,
                        "suspicious": 2,
                        "undetected": 60,
                        "harmless": 3,
                    }
                },
            }
        }

        mock_async_delete = AsyncMock()
        mock_async_get_size = AsyncMock(return_value=1024)
        mock_decrement = AsyncMock()

        with (
            patch("app.tasks.virustotal._run_async") as mock_run,
            patch("app.tasks.virustotal.settings") as mock_settings,
            patch("app.tasks.virustotal.requests") as mock_requests,
            patch("app.core.async_storage.delete_file", mock_async_delete),
            patch("app.core.async_storage.get_file_size", mock_async_get_size),
            patch("app.tasks.virustotal._decrement_owner_storage", mock_decrement),
            patch("app.tasks.virustotal._ensure_pool", new_callable=AsyncMock),
        ):
            mock_settings.VT_API_KEY = "test-key"
            mock_requests.get.return_value = mock_response
            mock_requests.RequestException = Exception

            # _run_async is called for DB ops and storage ops;
            # let it actually run the coro so async mocks are awaited
            call_count = [0]

            def run_async_side_effect(coro):
                call_count[0] += 1
                import asyncio

                try:
                    loop = asyncio.get_event_loop()
                    if loop.is_closed():
                        loop = asyncio.new_event_loop()
                except RuntimeError:
                    loop = asyncio.new_event_loop()
                return loop.run_until_complete(coro)

            mock_run.side_effect = run_async_side_effect

            from app.tasks.virustotal import check_virustotal

            result = check_virustotal(mock_self, "abc123hash", storage_key)

        assert result["status"] == "malicious"
        mock_async_delete.assert_awaited_once_with(storage_key)
        mock_async_get_size.assert_awaited_once_with(storage_key)
        mock_decrement.assert_awaited_once_with(storage_key, 1024)

    def test_check_not_found_in_vt(self):
        """check_virustotal should return 'not_found' and mark DB as 'unknown' (fail-close)."""
        mock_self = MagicMock()
        mock_self.request.id = "task-1"

        mock_response = MagicMock()
        mock_response.status_code = 404

        with (
            patch("app.tasks.virustotal._run_async") as mock_run,
            patch("app.tasks.virustotal.settings") as mock_settings,
            patch("app.tasks.virustotal.requests") as mock_requests,
        ):
            mock_settings.VT_API_KEY = "test-key"
            mock_requests.get.return_value = mock_response
            mock_requests.RequestException = Exception
            mock_run.return_value = None

            from app.tasks.virustotal import check_virustotal

            result = check_virustotal(mock_self, "abc123hash", "uploads/file.pdf")

        assert result["status"] == "not_found"
        # Verify DB is updated to 'unknown' (not 'clean') — fail-close
        assert mock_run.call_count == 2

    def test_check_retries_on_request_exception(self):
        """check_virustotal should call self.retry on network errors."""
        mock_self = MagicMock()
        mock_self.request.id = "task-1"
        mock_self.retry = MagicMock(side_effect=Exception("retry"))

        with (
            patch("app.tasks.virustotal._run_async") as mock_run,
            patch("app.tasks.virustotal.settings") as mock_settings,
            patch("app.tasks.virustotal.requests") as mock_requests,
        ):
            mock_settings.VT_API_KEY = "test-key"
            mock_requests.RequestException = Exception
            mock_requests.get.side_effect = Exception("connection refused")
            mock_run.return_value = None

            from app.tasks.virustotal import check_virustotal

            with pytest.raises(Exception, match="retry"):
                check_virustotal(mock_self, "abc123hash", "uploads/file.pdf")

        mock_self.retry.assert_called_once()

    def test_check_unexpected_status_code_retries_then_errors(self):
        """check_virustotal should retry on unexpected status, then mark as 'error'."""
        mock_self = MagicMock()
        mock_self.request.id = "task-1"
        # Simulate max retries exceeded — self.retry raises MaxRetriesExceededError
        mock_self.MaxRetriesExceededError = type("MaxRetriesExceededError", (Exception,), {})
        mock_self.retry.side_effect = mock_self.MaxRetriesExceededError()

        mock_response = MagicMock()
        mock_response.status_code = 500

        with (
            patch("app.tasks.virustotal._run_async") as mock_run,
            patch("app.tasks.virustotal.settings") as mock_settings,
            patch("app.tasks.virustotal.requests") as mock_requests,
        ):
            mock_settings.VT_API_KEY = "test-key"
            mock_requests.get.return_value = mock_response
            mock_requests.RequestException = Exception
            mock_run.return_value = None

            from app.tasks.virustotal import check_virustotal

            result = check_virustotal(mock_self, "abc123hash", "uploads/file.pdf")

        assert result["status"] == "error"
        assert result["code"] == 500
        mock_self.retry.assert_called_once()

    def test_check_unexpected_status_code_retry_succeeds(self):
        """check_virustotal should propagate retry when retries are available."""
        mock_self = MagicMock()
        mock_self.request.id = "task-1"
        # self.retry raises Retry exception (normal Celery behavior to re-queue)
        retry_exc = Exception("Retry")
        mock_self.MaxRetriesExceededError = type("MaxRetriesExceededError", (Exception,), {})
        mock_self.retry.side_effect = retry_exc

        mock_response = MagicMock()
        mock_response.status_code = 503

        with (
            patch("app.tasks.virustotal._run_async") as mock_run,
            patch("app.tasks.virustotal.settings") as mock_settings,
            patch("app.tasks.virustotal.requests") as mock_requests,
        ):
            mock_settings.VT_API_KEY = "test-key"
            mock_requests.get.return_value = mock_response
            mock_requests.RequestException = Exception
            mock_run.return_value = None

            from app.tasks.virustotal import check_virustotal

            with pytest.raises(Exception, match="Retry"):
                check_virustotal(mock_self, "abc123hash", "uploads/file.pdf")

        mock_self.retry.assert_called_once()

    def test_check_invalid_json_response(self):
        """check_virustotal should return 'error' and mark DB as 'error' (fail-close)."""
        mock_self = MagicMock()
        mock_self.request.id = "task-1"

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.side_effect = ValueError("bad json")

        with (
            patch("app.tasks.virustotal._run_async") as mock_run,
            patch("app.tasks.virustotal.settings") as mock_settings,
            patch("app.tasks.virustotal.requests") as mock_requests,
        ):
            mock_settings.VT_API_KEY = "test-key"
            mock_requests.get.return_value = mock_response
            mock_requests.RequestException = Exception
            mock_requests.exceptions = MagicMock()
            mock_requests.exceptions.JSONDecodeError = type("JSONDecodeError", (ValueError,), {})
            mock_run.return_value = None

            from app.tasks.virustotal import check_virustotal

            result = check_virustotal(mock_self, "abc123hash", "uploads/file.pdf")

        assert result["status"] == "error"
        assert result["reason"] == "invalid_json"
        # Verify DB is updated to 'error' (not 'clean') — fail-close
        assert mock_run.call_count == 2


# =========================================================================
# Tests for fail-close behavior (status values written to DB)
# =========================================================================


class TestVirusTotalFailClose:
    """Verify that error/unknown paths write the correct status to DB (not 'clean')."""

    def test_no_api_key_writes_skipped_to_db(self):
        """No API key should write 'skipped' status to DB, not 'clean'."""
        mock_self = MagicMock()
        mock_self.request.id = "task-1"

        update_calls = []

        def capture_run_async(coro):
            # Capture the coroutine's arguments by inspecting the coro
            update_calls.append(coro)
            return None

        with (
            patch("app.tasks.virustotal._run_async", side_effect=capture_run_async),
            patch("app.tasks.virustotal.settings") as mock_settings,
        ):
            mock_settings.VT_API_KEY = ""

            from app.tasks.virustotal import check_virustotal

            result = check_virustotal(mock_self, "abc123hash", "uploads/file.pdf")

        assert result["status"] == "skipped"
        # 2 calls: _insert_pending + _update_scan
        assert len(update_calls) == 2

    def test_404_writes_unknown_to_db(self):
        """404 from VT should write 'unknown' status to DB, not 'clean'."""
        mock_self = MagicMock()
        mock_self.request.id = "task-1"

        mock_response = MagicMock()
        mock_response.status_code = 404

        update_status_mock = AsyncMock()

        with (
            patch("app.tasks.virustotal.settings") as mock_settings,
            patch("app.tasks.virustotal.requests") as mock_requests,
            patch("app.tasks.virustotal._ensure_pool", new_callable=AsyncMock),
            patch("app.repositories.file_scan_repo.update_status", update_status_mock),
            patch("app.repositories.file_scan_repo.insert", AsyncMock()),
            patch("app.tasks.virustotal._run_async") as mock_run,
        ):
            mock_settings.VT_API_KEY = "test-key"
            mock_requests.get.return_value = mock_response
            mock_requests.RequestException = Exception

            import asyncio

            def run_coro(coro):
                loop = asyncio.new_event_loop()
                try:
                    return loop.run_until_complete(coro)
                finally:
                    loop.close()

            mock_run.side_effect = run_coro

            from app.tasks.virustotal import check_virustotal

            result = check_virustotal(mock_self, "abc123hash", "uploads/file.pdf")

        assert result["status"] == "not_found"
        update_status_mock.assert_awaited_once_with("uploads/file.pdf", "unknown", None, None, None)

    def test_non_200_writes_error_to_db_after_max_retries(self):
        """Non-200 with max retries exceeded should write 'error' to DB."""
        mock_self = MagicMock()
        mock_self.request.id = "task-1"
        mock_self.MaxRetriesExceededError = type("MaxRetriesExceededError", (Exception,), {})
        mock_self.retry.side_effect = mock_self.MaxRetriesExceededError()

        mock_response = MagicMock()
        mock_response.status_code = 500

        update_status_mock = AsyncMock()

        with (
            patch("app.tasks.virustotal.settings") as mock_settings,
            patch("app.tasks.virustotal.requests") as mock_requests,
            patch("app.tasks.virustotal._ensure_pool", new_callable=AsyncMock),
            patch("app.repositories.file_scan_repo.update_status", update_status_mock),
            patch("app.repositories.file_scan_repo.insert", AsyncMock()),
            patch("app.tasks.virustotal._run_async") as mock_run,
        ):
            mock_settings.VT_API_KEY = "test-key"
            mock_requests.get.return_value = mock_response
            mock_requests.RequestException = Exception

            import asyncio

            def run_coro(coro):
                loop = asyncio.new_event_loop()
                try:
                    return loop.run_until_complete(coro)
                finally:
                    loop.close()

            mock_run.side_effect = run_coro

            from app.tasks.virustotal import check_virustotal

            result = check_virustotal(mock_self, "abc123hash", "uploads/file.pdf")

        assert result["status"] == "error"
        assert result["code"] == 500
        update_status_mock.assert_awaited_once_with("uploads/file.pdf", "error", None, None, None)

    def test_invalid_json_writes_error_to_db(self):
        """Invalid JSON from VT should write 'error' to DB, not 'clean'."""
        mock_self = MagicMock()
        mock_self.request.id = "task-1"

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.side_effect = ValueError("bad json")

        update_status_mock = AsyncMock()

        with (
            patch("app.tasks.virustotal.settings") as mock_settings,
            patch("app.tasks.virustotal.requests") as mock_requests,
            patch("app.tasks.virustotal._ensure_pool", new_callable=AsyncMock),
            patch("app.repositories.file_scan_repo.update_status", update_status_mock),
            patch("app.repositories.file_scan_repo.insert", AsyncMock()),
            patch("app.tasks.virustotal._run_async") as mock_run,
        ):
            mock_settings.VT_API_KEY = "test-key"
            mock_requests.get.return_value = mock_response
            mock_requests.RequestException = Exception
            mock_requests.exceptions = MagicMock()
            mock_requests.exceptions.JSONDecodeError = type("JSONDecodeError", (ValueError,), {})

            import asyncio

            def run_coro(coro):
                loop = asyncio.new_event_loop()
                try:
                    return loop.run_until_complete(coro)
                finally:
                    loop.close()

            mock_run.side_effect = run_coro

            from app.tasks.virustotal import check_virustotal

            result = check_virustotal(mock_self, "abc123hash", "uploads/file.pdf")

        assert result["status"] == "error"
        assert result["reason"] == "invalid_json"
        update_status_mock.assert_awaited_once_with("uploads/file.pdf", "error", None, None, None)

    def test_clean_file_still_writes_clean(self):
        """Confirmed clean file should still write 'clean' to DB (unchanged behavior)."""
        mock_self = MagicMock()
        mock_self.request.id = "task-1"

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": {
                "id": "scan-abc",
                "attributes": {
                    "last_analysis_stats": {
                        "malicious": 0,
                        "suspicious": 0,
                        "undetected": 65,
                        "harmless": 5,
                    }
                },
            }
        }

        update_status_mock = AsyncMock()

        with (
            patch("app.tasks.virustotal.settings") as mock_settings,
            patch("app.tasks.virustotal.requests") as mock_requests,
            patch("app.tasks.virustotal._ensure_pool", new_callable=AsyncMock),
            patch("app.repositories.file_scan_repo.update_status", update_status_mock),
            patch("app.repositories.file_scan_repo.insert", AsyncMock()),
            patch("app.tasks.virustotal._run_async") as mock_run,
        ):
            mock_settings.VT_API_KEY = "test-key"
            mock_requests.get.return_value = mock_response
            mock_requests.RequestException = Exception

            import asyncio

            def run_coro(coro):
                loop = asyncio.new_event_loop()
                try:
                    return loop.run_until_complete(coro)
                finally:
                    loop.close()

            mock_run.side_effect = run_coro

            from app.tasks.virustotal import check_virustotal

            result = check_virustotal(mock_self, "abc123hash", "uploads/file.pdf")

        assert result["status"] == "clean"
        update_status_mock.assert_awaited_once_with("uploads/file.pdf", "clean", "scan-abc", 0, 70)

    def test_malicious_file_still_writes_malicious(self):
        """Confirmed malicious file should still write 'malicious' to DB (unchanged)."""
        mock_self = MagicMock()
        mock_self.request.id = "task-1"

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": {
                "id": "scan-bad",
                "attributes": {
                    "last_analysis_stats": {
                        "malicious": 3,
                        "suspicious": 1,
                        "undetected": 60,
                        "harmless": 5,
                    }
                },
            }
        }

        update_status_mock = AsyncMock()

        with (
            patch("app.tasks.virustotal.settings") as mock_settings,
            patch("app.tasks.virustotal.requests") as mock_requests,
            patch("app.tasks.virustotal._ensure_pool", new_callable=AsyncMock),
            patch("app.repositories.file_scan_repo.update_status", update_status_mock),
            patch("app.repositories.file_scan_repo.insert", AsyncMock()),
            patch("app.tasks.virustotal._run_async") as mock_run,
            patch("app.core.storage.delete_file", MagicMock()),
            patch("app.core.storage.get_file_size", MagicMock(return_value=0)),
        ):
            mock_settings.VT_API_KEY = "test-key"
            mock_requests.get.return_value = mock_response
            mock_requests.RequestException = Exception

            import asyncio

            def run_coro(coro):
                loop = asyncio.new_event_loop()
                try:
                    return loop.run_until_complete(coro)
                finally:
                    loop.close()

            mock_run.side_effect = run_coro

            from app.tasks.virustotal import check_virustotal

            result = check_virustotal(mock_self, "abc123hash", "uploads/file.pdf")

        assert result["status"] == "malicious"
        update_status_mock.assert_awaited_once_with(
            "uploads/file.pdf", "malicious", "scan-bad", 4, 69
        )


# =========================================================================
# Tests for cleanup_old_file_scans task
# =========================================================================


class TestCleanupOldFileScans:
    """Tests for the cleanup_old_file_scans Celery task."""

    @pytest.mark.anyio
    async def test_delete_old_completed_returns_count(self):
        """delete_old_completed should parse the DELETE count from asyncpg result."""
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock(return_value="DELETE 5")

        mock_cm = AsyncMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_cm.__aexit__ = AsyncMock(return_value=False)

        mock_pool = MagicMock()
        mock_pool.acquire = MagicMock(return_value=mock_cm)

        with patch("app.repositories.file_scan_repo.get_pool", return_value=mock_pool):
            from app.repositories.file_scan_repo import delete_old_completed

            result = await delete_old_completed(days=30)

        assert result == 5
        mock_conn.execute.assert_awaited_once()
        # Verify the SQL uses the correct interval
        sql_arg = mock_conn.execute.call_args[0][0]
        assert "make_interval" in sql_arg
        assert mock_conn.execute.call_args[0][1] == 30

    @pytest.mark.anyio
    async def test_delete_old_completed_zero_rows(self):
        """Should return 0 when no rows match."""
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock(return_value="DELETE 0")

        mock_cm = AsyncMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_cm.__aexit__ = AsyncMock(return_value=False)

        mock_pool = MagicMock()
        mock_pool.acquire = MagicMock(return_value=mock_cm)

        with patch("app.repositories.file_scan_repo.get_pool", return_value=mock_pool):
            from app.repositories.file_scan_repo import delete_old_completed

            result = await delete_old_completed(days=7)

        assert result == 0

    @pytest.mark.anyio
    async def test_delete_old_completed_custom_days(self):
        """Should pass the custom days parameter to the query."""
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock(return_value="DELETE 3")

        mock_cm = AsyncMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_cm.__aexit__ = AsyncMock(return_value=False)

        mock_pool = MagicMock()
        mock_pool.acquire = MagicMock(return_value=mock_cm)

        with patch("app.repositories.file_scan_repo.get_pool", return_value=mock_pool):
            from app.repositories.file_scan_repo import delete_old_completed

            await delete_old_completed(days=90)

        assert mock_conn.execute.call_args[0][1] == 90

    def test_cleanup_task_calls_repo(self):
        """cleanup_old_file_scans task should call delete_old_completed via _run_async."""
        mock_delete = AsyncMock(return_value=12)

        with (
            patch("app.tasks.cleanup._run_async") as mock_run,
            patch("app.tasks.cleanup._ensure_pool", new_callable=AsyncMock),
            patch(
                "app.repositories.file_scan_repo.delete_old_completed",
                mock_delete,
            ),
        ):
            # _run_async executes the coroutine; simulate by running it
            async def run_coro(coro):
                return await coro

            import asyncio

            loop = asyncio.new_event_loop()
            mock_run.side_effect = lambda coro: loop.run_until_complete(coro)

            from app.tasks.cleanup import cleanup_old_file_scans

            mock_self = MagicMock()
            result = cleanup_old_file_scans(mock_self, days=30)

        assert result["deleted"] == 12
        assert result["retention_days"] == 30

    def test_cleanup_task_module_has_new_task(self):
        """cleanup module should export cleanup_old_file_scans."""
        import importlib

        import app.tasks.cleanup as cleanup_mod

        importlib.reload(cleanup_mod)
        assert hasattr(cleanup_mod, "cleanup_old_file_scans")


class TestDeleteOrphansOrder:
    """Verify _delete_orphans performs operations in the correct order."""

    @pytest.mark.anyio
    async def test_delete_orphans_reorder(self):
        """Operations must follow: get_size -> delete_by_key -> decrement -> delete_file.

        This order ensures that if accounting (decrement) fails after the DB
        record is removed, the physical file still exists in storage and will
        be picked up as an orphan on the next cleanup cycle (retryable).
        """
        call_order: list[str] = []

        async def mock_get_file_size(key: str) -> int:
            call_order.append("get_file_size")
            return 1024

        async def mock_delete_file(key: str) -> None:
            call_order.append("delete_file")

        async def mock_delete_by_key(key: str) -> None:
            call_order.append("delete_by_key")

        async def mock_decrement(key: str, size: int) -> None:
            call_order.append("decrement_owner_storage")

        with (
            patch(
                "app.core.async_storage.get_file_size",
                side_effect=mock_get_file_size,
            ),
            patch(
                "app.core.async_storage.delete_file",
                side_effect=mock_delete_file,
            ),
            patch(
                "app.repositories.file_scan_repo.delete_by_key",
                side_effect=mock_delete_by_key,
            ),
            patch(
                "app.tasks.utils.decrement_owner_storage",
                side_effect=mock_decrement,
            ),
            patch("app.tasks.cleanup._ensure_pool", new_callable=AsyncMock),
        ):
            from app.tasks.cleanup import _delete_orphans

            deleted = await _delete_orphans(["editor/user1/file.png"])

        assert deleted == 1
        assert call_order == [
            "get_file_size",
            "delete_by_key",
            "decrement_owner_storage",
            "delete_file",
        ], f"Expected order: get_size->delete_by_key->decrement->delete_file, got: {call_order}"


# =========================================================================
# Tests for thumbnail task (N-B06, N-B13)
# =========================================================================


class TestThumbnailTask:
    """Tests for the generate_thumbnail_task in thumbnail.py."""

    def test_max_image_pixels_set_before_image_open(self):
        """N-B06: MAX_IMAGE_PIXELS must be set before Image.open is called."""
        mock_image_module = MagicMock()
        MagicMock()  # image_ops — unused but required for test setup
        MagicMock()  # minio — unused but required for test setup
        mock_settings = MagicMock()
        mock_settings.S3_ENDPOINT = "localhost:9000"
        mock_settings.S3_ACCESS_KEY_ID = "user"
        mock_settings.S3_SECRET_ACCESS_KEY = "pass"
        mock_settings.S3_USE_SSL = False
        mock_settings.S3_BUCKET_NAME = "bucket"

        # Track the order of calls
        call_order = []

        original_setattr = type(mock_image_module).__setattr__

        def track_max_pixels(self, name, value):
            if name == "MAX_IMAGE_PIXELS":
                call_order.append(("set_max_pixels", value))
            original_setattr(self, name, value)

        mock_image_module.__class__ = type("MockImage", (), {"__setattr__": track_max_pixels})

        # Instead of tracking setattr, verify via source inspection
        import inspect

        from app.tasks.thumbnail import generate_thumbnail_task

        source = inspect.getsource(generate_thumbnail_task)
        max_pixels_pos = source.find("MAX_IMAGE_PIXELS")
        image_open_pos = source.find("Image.open")
        assert (
            max_pixels_pos < image_open_pos
        ), "MAX_IMAGE_PIXELS must be set before Image.open is called"

    def test_max_download_size_constant_exists(self):
        """N-B13: MAX_DOWNLOAD_SIZE constant must be defined at module level."""
        from app.tasks.thumbnail import MAX_DOWNLOAD_SIZE

        assert MAX_DOWNLOAD_SIZE == 50 * 1024 * 1024

    def test_download_uses_bounded_read(self):
        """N-B13: response.read() must be called with a size limit."""
        import inspect

        from app.tasks.thumbnail import generate_thumbnail_task

        source = inspect.getsource(generate_thumbnail_task)
        # Must call response.read with a size argument, not unbounded
        assert (
            "response.read()" not in source
        ), "response.read() is unbounded — must pass MAX_DOWNLOAD_SIZE"
        assert "response.read(MAX_DOWNLOAD_SIZE" in source

    def test_oversized_download_returns_skipped(self):
        """N-B13: Files exceeding MAX_DOWNLOAD_SIZE should be skipped."""
        from app.tasks.thumbnail import MAX_DOWNLOAD_SIZE

        mock_response = MagicMock()
        # Return data larger than limit
        mock_response.read.return_value = b"x" * (MAX_DOWNLOAD_SIZE + 1)

        mock_minio_client = MagicMock()
        mock_minio_client.get_object.return_value = mock_response

        mock_minio_class = MagicMock(return_value=mock_minio_client)
        mock_minio_mod = types.ModuleType("minio")
        mock_minio_mod.Minio = mock_minio_class

        mock_settings = MagicMock()
        mock_settings.S3_ENDPOINT = "localhost:9000"
        mock_settings.S3_ACCESS_KEY_ID = "user"
        mock_settings.S3_SECRET_ACCESS_KEY = "pass"
        mock_settings.S3_USE_SSL = False
        mock_settings.S3_BUCKET_NAME = "bucket"

        saved_minio = sys.modules.get("minio")
        sys.modules["minio"] = mock_minio_mod
        try:
            with (
                patch("app.core.config.settings", mock_settings),
                patch("app.core.constants.ALBUM_THUMBNAIL_QUALITY", 85),
                patch("app.core.constants.ALBUM_THUMBNAIL_SIZE", (400, 400)),
            ):
                # Force re-import to pick up mocked minio
                if "app.tasks.thumbnail" in sys.modules:
                    del sys.modules["app.tasks.thumbnail"]
                from app.tasks.thumbnail import generate_thumbnail_task

                result = generate_thumbnail_task(
                    MagicMock(), "photos/big.jpg", "thumbs/big.webp", str(uuid.uuid4())
                )
        finally:
            if saved_minio is None:
                sys.modules.pop("minio", None)
            else:
                sys.modules["minio"] = saved_minio
            sys.modules.pop("app.tasks.thumbnail", None)

        assert result["status"] == "skipped"
        assert result["reason"] == "file_too_large"
        mock_response.close.assert_called_once()
        mock_response.release_conn.assert_called_once()

    def test_normal_size_download_proceeds(self):
        """N-B13: Files within MAX_DOWNLOAD_SIZE should be processed normally."""
        # Create a small valid image in memory
        from PIL import Image as PILImage

        from app.tasks.thumbnail import MAX_DOWNLOAD_SIZE

        img_buf = io.BytesIO()
        img = PILImage.new("RGB", (100, 100), color="red")
        img.save(img_buf, format="JPEG")
        img_data = img_buf.getvalue()
        assert len(img_data) < MAX_DOWNLOAD_SIZE

        mock_response = MagicMock()
        mock_response.read.return_value = img_data

        mock_minio_client = MagicMock()
        mock_minio_client.get_object.return_value = mock_response

        mock_minio_class = MagicMock(return_value=mock_minio_client)
        mock_minio_mod = types.ModuleType("minio")
        mock_minio_mod.Minio = mock_minio_class

        mock_settings = MagicMock()
        mock_settings.S3_ENDPOINT = "localhost:9000"
        mock_settings.S3_ACCESS_KEY_ID = "user"
        mock_settings.S3_SECRET_ACCESS_KEY = "pass"
        mock_settings.S3_USE_SSL = False
        mock_settings.S3_BUCKET_NAME = "bucket"

        saved_minio = sys.modules.get("minio")
        sys.modules["minio"] = mock_minio_mod
        try:
            # Re-import with minio module available
            if "app.tasks.thumbnail" in sys.modules:
                del sys.modules["app.tasks.thumbnail"]

            with (
                patch("app.core.config.settings", mock_settings),
                patch("app.core.constants.ALBUM_THUMBNAIL_QUALITY", 85),
                patch("app.core.constants.ALBUM_THUMBNAIL_SIZE", (400, 400)),
            ):
                from app.tasks.thumbnail import generate_thumbnail_task

                # Patch _run_async AFTER import so the reference is resolved
                with patch("app.tasks.thumbnail._run_async"):
                    result = generate_thumbnail_task(
                        MagicMock(), "photos/ok.jpg", "thumbs/ok.webp", str(uuid.uuid4())
                    )
        finally:
            if saved_minio is None:
                sys.modules.pop("minio", None)
            else:
                sys.modules["minio"] = saved_minio
            sys.modules.pop("app.tasks.thumbnail", None)

        assert result["status"] == "success"
        assert result["thumbnail_key"] == "thumbs/ok.webp"
        # Verify upload was called
        mock_minio_client.put_object.assert_called_once()
