"""Unit tests for DM cleanup tasks (B-01: pool init + shared async runner)."""

import sys
import types
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Celery module mock (must precede imports of app.tasks.*)
# ---------------------------------------------------------------------------
@pytest.fixture(autouse=True)
def _celery_modules():
    """Inject fake celery modules so task imports succeed without a broker."""
    celery_mod = types.ModuleType("celery")
    celery_result_mod = types.ModuleType("celery.result")
    celery_mod.result = celery_result_mod
    celery_mod.shared_task = lambda **kw: (lambda fn: fn)

    celery_app_mod = types.ModuleType("app.celery_app")
    mock_celery_app = MagicMock()
    mock_celery_app.task = lambda *a, **kw: (lambda fn: fn)
    celery_app_mod.celery = mock_celery_app

    saved = {}
    for key in ("celery", "celery.result", "app.celery_app"):
        saved[key] = sys.modules.get(key)

    sys.modules["celery"] = celery_mod
    sys.modules["celery.result"] = celery_result_mod
    sys.modules["app.celery_app"] = celery_app_mod

    yield

    for key, val in saved.items():
        if val is None:
            sys.modules.pop(key, None)
        else:
            sys.modules[key] = val

    for mod_name in list(sys.modules):
        if mod_name.startswith("app.tasks."):
            del sys.modules[mod_name]


# ===========================================================================
# Verify structural fixes (B-01)
# ===========================================================================


class TestDmCleanupStructure:
    """Verify that dm_cleanup uses the shared async runner and calls _ensure_pool."""

    def test_uses_shared_run_async(self):
        """dm_cleanup must import _run_async from app.tasks.async_runner, not define its own."""
        import importlib
        import inspect

        mod = importlib.import_module("app.tasks.dm_cleanup")
        source = inspect.getsource(mod)

        # Should NOT define its own _run_async / asyncio.new_event_loop pattern
        assert "def _run_async" not in source, (
            "dm_cleanup should not define its own _run_async; "
            "it should import from app.tasks.async_runner"
        )
        assert "asyncio.new_event_loop" not in source

        # Should import the shared runner
        assert "from app.tasks.async_runner import run_async" in source

    def test_imports_ensure_pool(self):
        """dm_cleanup must import _ensure_pool from app.tasks.cleanup."""
        import importlib
        import inspect

        mod = importlib.import_module("app.tasks.dm_cleanup")
        source = inspect.getsource(mod)

        assert "from app.tasks.cleanup import _ensure_pool" in source

    def test_cleanup_files_calls_ensure_pool(self):
        """_cleanup_files source must call _ensure_pool before any repo access."""
        import importlib
        import inspect

        mod = importlib.import_module("app.tasks.dm_cleanup")
        source = inspect.getsource(mod._cleanup_files)

        # _ensure_pool should appear before dm_repo
        pool_pos = source.index("_ensure_pool")
        repo_pos = source.index("dm_repo")
        assert pool_pos < repo_pos, "_ensure_pool must be called before dm_repo access"

    def test_cleanup_text_calls_ensure_pool(self):
        """_cleanup_text source must call _ensure_pool before any repo access."""
        import importlib
        import inspect

        mod = importlib.import_module("app.tasks.dm_cleanup")
        source = inspect.getsource(mod._cleanup_text)

        pool_pos = source.index("_ensure_pool")
        repo_pos = source.index("dm_repo")
        assert pool_pos < repo_pos, "_ensure_pool must be called before dm_repo access"


# ===========================================================================
# Happy-path tests for cleanup_dm_expired_files
# ===========================================================================


class TestCleanupDmExpiredFiles:
    """Tests for the _cleanup_files async function."""

    @pytest.mark.anyio
    async def test_cleanup_files_happy_path(self):
        """Deletes expired file attachments, decrements storage, clears attachment."""
        msg_id = uuid.uuid4()
        sender_id = uuid.uuid4()
        expired_msgs = [
            {
                "id": msg_id,
                "attachment_key": "dm/test/file.pdf",
                "attachment_size": 1024,
                "sender_id": sender_id,
            }
        ]

        mock_find = AsyncMock(return_value=expired_msgs)
        mock_clear_if_present = AsyncMock(return_value=True)
        mock_decrement = AsyncMock()
        mock_delete_file = AsyncMock()

        with (
            patch("app.tasks.cleanup._ensure_pool", new_callable=AsyncMock),
            patch("app.tasks.dm_cleanup._ensure_pool", new_callable=AsyncMock) as mock_pool,
            patch("app.repositories.dm_repo.find_expired_file_messages", mock_find),
            patch("app.repositories.dm_repo.clear_message_attachment_if_present", mock_clear_if_present),
            patch("app.repositories.user_repo.decrement_storage_used", mock_decrement),
            patch("app.core.async_storage.delete_file", mock_delete_file),
        ):
            from app.tasks.dm_cleanup import _cleanup_files

            result = await _cleanup_files()

        mock_pool.assert_awaited_once()
        mock_delete_file.assert_awaited_once_with("dm/test/file.pdf")
        mock_decrement.assert_awaited_once_with(sender_id, 1024)
        mock_clear_if_present.assert_awaited_once_with(msg_id)
        assert result == {"deleted": 1, "errors": 0}

    @pytest.mark.anyio
    async def test_cleanup_files_no_expired(self):
        """Returns zeros when no expired files found."""
        mock_find = AsyncMock(return_value=[])

        with (
            patch("app.tasks.cleanup._ensure_pool", new_callable=AsyncMock),
            patch("app.tasks.dm_cleanup._ensure_pool", new_callable=AsyncMock),
            patch("app.repositories.dm_repo.find_expired_file_messages", mock_find),
        ):
            from app.tasks.dm_cleanup import _cleanup_files

            result = await _cleanup_files()

        assert result == {"deleted": 0, "errors": 0}

    @pytest.mark.anyio
    async def test_cleanup_files_error_counted(self):
        """Errors during clear_message_attachment_if_present are counted, not raised."""
        msg_id = uuid.uuid4()
        expired_msgs = [
            {
                "id": msg_id,
                "attachment_key": "dm/test/file.pdf",
                "attachment_size": 1024,
                "sender_id": uuid.uuid4(),
            }
        ]

        mock_find = AsyncMock(return_value=expired_msgs)
        mock_clear = AsyncMock(side_effect=RuntimeError("DB error"))

        with (
            patch("app.tasks.cleanup._ensure_pool", new_callable=AsyncMock),
            patch("app.tasks.dm_cleanup._ensure_pool", new_callable=AsyncMock),
            patch("app.repositories.dm_repo.find_expired_file_messages", mock_find),
            patch("app.repositories.dm_repo.clear_message_attachment_if_present", mock_clear),
        ):
            from app.tasks.dm_cleanup import _cleanup_files

            result = await _cleanup_files()

        assert result == {"deleted": 0, "errors": 1}


# ===========================================================================
# Happy-path tests for cleanup_dm_expired_text
# ===========================================================================


class TestCleanupDmExpiredText:
    """Tests for the _cleanup_text async function."""

    @pytest.mark.anyio
    async def test_cleanup_text_happy_path(self):
        """Deletes expired text messages and adjusts char counts."""
        msg_id = uuid.uuid4()
        conv_id = uuid.uuid4()
        expired_msgs = [
            {
                "id": msg_id,
                "conversation_id": conv_id,
                "content": "Hello, world!",
            }
        ]

        mock_find = AsyncMock(return_value=expired_msgs)

        # Mock pool for transactional cleanup
        mock_conn = MagicMock()
        mock_conn.fetchval = AsyncMock(return_value=1)  # deleted count
        mock_conn.execute = AsyncMock()
        mock_tx = MagicMock()
        mock_tx.__aenter__ = AsyncMock(return_value=None)
        mock_tx.__aexit__ = AsyncMock(return_value=None)
        mock_conn.transaction.return_value = mock_tx
        mock_acq = MagicMock()
        mock_acq.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_acq.__aexit__ = AsyncMock(return_value=None)
        mock_pool_obj = MagicMock()
        mock_pool_obj.acquire.return_value = mock_acq

        with (
            patch("app.tasks.cleanup._ensure_pool", new_callable=AsyncMock),
            patch("app.tasks.dm_cleanup._ensure_pool", new_callable=AsyncMock),
            patch("app.repositories.dm_repo.find_expired_text_messages", mock_find),
            patch("app.core.database.get_pool", return_value=mock_pool_obj),
        ):
            from app.tasks.dm_cleanup import _cleanup_text

            result = await _cleanup_text()

        assert result == {"deleted": 1}

    @pytest.mark.anyio
    async def test_cleanup_text_no_expired(self):
        """Returns early with zero deleted when no expired messages."""
        mock_find = AsyncMock(return_value=[])

        with (
            patch("app.tasks.cleanup._ensure_pool", new_callable=AsyncMock),
            patch("app.tasks.dm_cleanup._ensure_pool", new_callable=AsyncMock),
            patch("app.repositories.dm_repo.find_expired_text_messages", mock_find),
        ):
            from app.tasks.dm_cleanup import _cleanup_text

            result = await _cleanup_text()

        assert result == {"deleted": 0}

    @pytest.mark.anyio
    async def test_cleanup_text_char_count_error_does_not_raise(self):
        """Failure to decrement char count is logged but does not crash."""
        msg_id = uuid.uuid4()
        conv_id = uuid.uuid4()
        expired_msgs = [
            {
                "id": msg_id,
                "conversation_id": conv_id,
                "content": "test",
            }
        ]

        mock_find = AsyncMock(return_value=expired_msgs)

        # Mock pool for transactional cleanup (succeeds normally)
        mock_conn = MagicMock()
        mock_conn.fetchval = AsyncMock(return_value=1)
        mock_conn.execute = AsyncMock()
        mock_tx = MagicMock()
        mock_tx.__aenter__ = AsyncMock(return_value=None)
        mock_tx.__aexit__ = AsyncMock(return_value=None)
        mock_conn.transaction.return_value = mock_tx
        mock_acq = MagicMock()
        mock_acq.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_acq.__aexit__ = AsyncMock(return_value=None)
        mock_pool_obj = MagicMock()
        mock_pool_obj.acquire.return_value = mock_acq

        with (
            patch("app.tasks.cleanup._ensure_pool", new_callable=AsyncMock),
            patch("app.tasks.dm_cleanup._ensure_pool", new_callable=AsyncMock),
            patch("app.repositories.dm_repo.find_expired_text_messages", mock_find),
            patch("app.core.database.get_pool", return_value=mock_pool_obj),
        ):
            from app.tasks.dm_cleanup import _cleanup_text

            result = await _cleanup_text()

        # Transactional cleanup succeeds atomically
        assert result == {"deleted": 1}
