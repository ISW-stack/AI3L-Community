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


class TestAsyncRetry:
    """Tests for the _async_retry coroutine in event_retry.py."""

    @pytest.mark.anyio
    async def test_noop_when_no_failed_events(self):
        """Should return early when Redis has no failed events."""
        mock_redis = AsyncMock()
        mock_redis.lrange = AsyncMock(return_value=[])

        with patch("app.core.redis.get_redis", return_value=mock_redis):
            from app.tasks.event_retry import _async_retry

            await _async_retry()

        mock_redis.lrange.assert_awaited_once_with("event_bus:failed", 0, -1)
        mock_redis.delete.assert_not_awaited()

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
        event_entry = json.dumps(
            {
                "event": "test.event",
                "handler": "my_handler",
                "kwargs": {"user_id": "abc"},
                "retry_count": 0,
            }
        )

        mock_redis = AsyncMock()
        mock_redis.lrange = AsyncMock(return_value=[event_entry])
        mock_redis.delete = AsyncMock()

        with (
            patch("app.core.redis.get_redis", return_value=mock_redis),
            patch.dict("app.core.event_bus._handlers", {"test.event": [handler]}),
        ):
            from app.tasks.event_retry import _async_retry

            await _async_retry()

        handler.assert_awaited_once_with(user_id="abc")
        mock_redis.delete.assert_awaited_once_with("event_bus:failed")

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
        mock_redis.lrange = AsyncMock(return_value=[event_entry])
        mock_redis.delete = AsyncMock()

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
        mock_redis.lrange = AsyncMock(return_value=["not-valid-json{{{"])
        mock_redis.delete = AsyncMock()

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
        mock_redis.lrange = AsyncMock(return_value=[event_entry])
        mock_redis.delete = AsyncMock()

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
        event_entry = json.dumps(
            {
                "event": "test.event",
                "handler": "my_handler",
                "kwargs": {"x": 1},
                "retry_count": 1,
            }
        )

        mock_redis = AsyncMock()
        mock_redis.lrange = AsyncMock(return_value=[event_entry])
        mock_redis.delete = AsyncMock()

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
        mock_redis.lrange = AsyncMock(return_value=[event_entry])
        mock_redis.delete = AsyncMock()

        with patch("app.core.redis.get_redis", return_value=mock_redis):
            from app.tasks.event_retry import _async_retry

            await _async_retry()

    @pytest.mark.anyio
    async def test_multiple_events_mixed_outcomes(self):
        """Process multiple events: one succeeds, one dropped (max retries), one fails."""
        good_handler = AsyncMock()
        bad_handler = AsyncMock(side_effect=RuntimeError("fail"))

        events = [
            json.dumps({"event": "good", "handler": "h", "kwargs": {}, "retry_count": 0}),
            json.dumps({"event": "maxed", "handler": "h", "kwargs": {}, "retry_count": 3}),
            json.dumps({"event": "bad", "handler": "h_bad", "kwargs": {}, "retry_count": 0}),
        ]

        mock_redis = AsyncMock()
        mock_redis.lrange = AsyncMock(return_value=events)
        mock_redis.delete = AsyncMock()

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
            patch("app.tasks.virustotal.get_pool", return_value=MagicMock()),
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
            patch("app.tasks.virustotal.get_pool", return_value=MagicMock()),
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
            patch("app.tasks.virustotal.get_pool", side_effect=RuntimeError("no pool")),
            patch("app.tasks.virustotal.init_db_pool", mock_init),
        ):
            from app.tasks.virustotal import _ensure_pool

            await _ensure_pool()

        mock_init.assert_awaited_once()

    @pytest.mark.anyio
    async def test_ensure_pool_noop_when_available(self):
        """_ensure_pool should not call init_db_pool when pool exists."""
        mock_init = AsyncMock()

        with (
            patch("app.tasks.virustotal.get_pool", return_value=MagicMock()),
            patch("app.tasks.virustotal.init_db_pool", mock_init),
        ):
            from app.tasks.virustotal import _ensure_pool

            await _ensure_pool()

        mock_init.assert_not_awaited()

    def test_check_skipped_when_no_api_key(self):
        """check_virustotal should return 'skipped' when VT_API_KEY is empty."""
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

        mock_delete = MagicMock()
        mock_get_size = MagicMock(return_value=0)

        with (
            patch("app.tasks.virustotal._run_async") as mock_run,
            patch("app.tasks.virustotal.settings") as mock_settings,
            patch("app.tasks.virustotal.requests") as mock_requests,
            patch("app.core.storage.delete_file", mock_delete),
            patch("app.core.storage.get_file_size", mock_get_size),
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
        mock_delete.assert_called_once_with("uploads/malware.exe")

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

        mock_delete = MagicMock()
        mock_get_size = MagicMock(return_value=1024)
        mock_decrement = AsyncMock()

        with (
            patch("app.tasks.virustotal._run_async") as mock_run,
            patch("app.tasks.virustotal.settings") as mock_settings,
            patch("app.tasks.virustotal.requests") as mock_requests,
            patch("app.core.storage.delete_file", mock_delete),
            patch("app.core.storage.get_file_size", mock_get_size),
            patch("app.repositories.user_repo.increment_storage_used", mock_decrement),
            patch("app.tasks.virustotal.get_pool", return_value=MagicMock()),
        ):
            mock_settings.VT_API_KEY = "test-key"
            mock_requests.get.return_value = mock_response
            mock_requests.RequestException = Exception

            # _run_async is called for DB ops; let it actually run the coro for decrement
            call_count = [0]

            def run_async_side_effect(coro):
                call_count[0] += 1
                # The first calls are for _insert_pending and _update_scan (return None)
                # The last call is for _decrement_owner_storage
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
        mock_delete.assert_called_once_with(storage_key)
        mock_get_size.assert_called_once_with(storage_key)
        mock_decrement.assert_awaited_once_with(uuid.UUID(user_id), -1024)

    def test_check_not_found_in_vt(self):
        """check_virustotal should return 'not_found' for 404 responses."""
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

    def test_check_unexpected_status_code(self):
        """check_virustotal should return 'error' for unexpected HTTP status codes."""
        mock_self = MagicMock()
        mock_self.request.id = "task-1"

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

    def test_check_invalid_json_response(self):
        """check_virustotal should return 'error' when VT returns invalid JSON."""
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

            mock_run.side_effect = lambda coro: asyncio.get_event_loop().run_until_complete(coro)

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
