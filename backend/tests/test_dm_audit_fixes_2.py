"""Tests for DM audit fixes batch 2:

H-03: edit_message bypasses conversation char cap
H-07: WS failure blocks DB notification in event handler
H-08: Conversation list attachment_key always null
M-05: Friendship check and send_message_atomic in separate transactions
M-18: DM text cleanup race condition (advisory lock)
M-19: Recalled message content not stripped by converter
M-24: _DEFAULTS missing dm_friends_only
L-12: No orphan file cleaner for dm/ prefix
L-16: DM attachment filename stored unsanitized
"""

import os
import re
import sys
import types
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.errors import AppError

_NOW = datetime.now(timezone.utc)
_SENDER_ID = str(uuid.uuid4())
_RECIPIENT_ID = str(uuid.uuid4())
_CONV_ID = uuid.uuid4()
_MSG_ID = uuid.uuid4()


def _make_message_row(
    msg_id=None,
    conv_id=None,
    sender_id=None,
    content="Hello!",
    is_recalled=False,
    is_edited=False,
    attachment_key=None,
    attachment_name=None,
    attachment_size=None,
    attachment_expires_at=None,
    created_at=None,
):
    return {
        "id": msg_id or uuid.uuid4(),
        "conversation_id": conv_id or _CONV_ID,
        "sender_id": uuid.UUID(sender_id) if sender_id else uuid.uuid4(),
        "content": content,
        "attachment_key": attachment_key,
        "attachment_name": attachment_name,
        "attachment_size": attachment_size,
        "attachment_expires_at": attachment_expires_at,
        "is_recalled": is_recalled,
        "is_edited": is_edited,
        "read_at": None,
        "created_at": created_at or _NOW,
        "updated_at": _NOW,
        "sender_display_name": "Test User",
        "sender_avatar_url": None,
    }


def _make_conversation(conv_id=None, user_a=None, user_b=None, total_chars=0):
    return {
        "id": conv_id or uuid.uuid4(),
        "participant_a": uuid.UUID(user_a) if user_a else uuid.uuid4(),
        "participant_b": uuid.UUID(user_b) if user_b else uuid.uuid4(),
        "total_chars": total_chars,
        "created_at": _NOW,
        "updated_at": _NOW,
    }


def _mock_pool_conn():
    """Create a mock pool with acquire() context manager returning a mock conn."""
    pool = MagicMock()
    conn = MagicMock()
    conn.fetchrow = AsyncMock(return_value=None)
    conn.fetch = AsyncMock(return_value=[])
    conn.fetchval = AsyncMock(return_value=None)
    conn.execute = AsyncMock(return_value="UPDATE 1")

    tx = MagicMock()
    tx.__aenter__ = AsyncMock(return_value=None)
    tx.__aexit__ = AsyncMock(return_value=None)
    conn.transaction = MagicMock(return_value=tx)

    acq = MagicMock()
    acq.__aenter__ = AsyncMock(return_value=conn)
    acq.__aexit__ = AsyncMock(return_value=None)
    pool.acquire.return_value = acq

    return pool, conn


# ===========================================================================
# H-03: edit_message bypasses conversation char cap
# ===========================================================================


class TestH03EditCharCap:
    """H-03: edit_message must check char cap when content grows."""

    @pytest.mark.anyio
    @patch("app.core.database.get_pool")
    @patch("app.services.dm.async_row_to_message", new_callable=AsyncMock)
    @patch("app.services.dm.emit", new_callable=AsyncMock)
    @patch("app.services.dm.dm_repo")
    async def test_edit_exceeding_char_cap_rejected(
        self, mock_dm_repo, mock_emit, mock_convert, mock_get_pool
    ):
        """Editing a message to exceed the char cap should raise 400."""
        from app.core.constants import DM_CHAR_CAP_PER_CONVERSATION

        msg_row = _make_message_row(sender_id=_SENDER_ID, content="Hi", created_at=_NOW)

        pool, conn = _mock_pool_conn()

        # fetchrow #1: SELECT ... FOR UPDATE (returns the message)
        # fetchval #1: advisory lock (returns None)
        # fetchval #2: total_chars (near cap)
        call_count = 0

        async def mock_fetchval(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            sql = args[0] if args else ""
            if "pg_advisory_xact_lock" in sql:
                return None
            if "total_chars" in sql:
                return DM_CHAR_CAP_PER_CONVERSATION - 1  # only 1 char left
            return None

        conn.fetchrow = AsyncMock(return_value=msg_row)
        conn.fetchval = AsyncMock(side_effect=mock_fetchval)
        mock_get_pool.return_value = pool

        from app.services.dm import edit_message

        # New content is much longer than old "Hi" (delta > 1 available)
        with pytest.raises(AppError) as exc_info:
            await edit_message(str(_MSG_ID), _SENDER_ID, "A much longer replacement message")

        assert exc_info.value.status_code == 400
        assert "character cap" in exc_info.value.detail["message"].lower()

    @pytest.mark.anyio
    @patch("app.core.database.get_pool")
    @patch("app.services.dm.async_row_to_message", new_callable=AsyncMock)
    @patch("app.services.dm.emit", new_callable=AsyncMock)
    @patch("app.services.dm.dm_repo")
    async def test_edit_within_char_cap_allowed(
        self, mock_dm_repo, mock_emit, mock_convert, mock_get_pool
    ):
        """Editing within the char cap should succeed."""
        from app.core.constants import DM_CHAR_CAP_PER_CONVERSATION

        msg_row = _make_message_row(sender_id=_SENDER_ID, content="Hello", created_at=_NOW)
        updated_row = _make_message_row(
            sender_id=_SENDER_ID, content="Hello world", is_edited=True
        )
        conv = _make_conversation(
            conv_id=msg_row["conversation_id"],
            user_a=_SENDER_ID,
            user_b=_RECIPIENT_ID,
        )

        pool, conn = _mock_pool_conn()

        async def mock_fetchval(*args, **kwargs):
            sql = args[0] if args else ""
            if "pg_advisory_xact_lock" in sql:
                return None
            if "total_chars" in sql:
                return 100  # plenty of room
            return None

        conn.fetchrow = AsyncMock(side_effect=[msg_row, updated_row])
        conn.fetchval = AsyncMock(side_effect=mock_fetchval)
        mock_get_pool.return_value = pool

        mock_dm_repo.find_conversation_by_id = AsyncMock(return_value=conv)
        mock_convert.return_value = {
            "id": str(_MSG_ID),
            "conversation_id": str(_CONV_ID),
            "sender": {"id": _SENDER_ID, "display_name": "Test", "avatar_url": None},
            "content": "Hello world",
            "attachment_url": None,
            "attachment_name": None,
            "attachment_size": None,
            "attachment_expires_at": None,
            "is_recalled": False,
            "is_edited": True,
            "read_at": None,
            "created_at": _NOW.isoformat(),
            "updated_at": _NOW.isoformat(),
        }

        from app.services.dm import edit_message

        result = await edit_message(str(_MSG_ID), _SENDER_ID, "Hello world")
        assert result["content"] == "Hello world"

    @pytest.mark.anyio
    @patch("app.core.database.get_pool")
    @patch("app.services.dm.async_row_to_message", new_callable=AsyncMock)
    @patch("app.services.dm.emit", new_callable=AsyncMock)
    @patch("app.services.dm.dm_repo")
    async def test_edit_shrinking_content_skips_cap_check(
        self, mock_dm_repo, mock_emit, mock_convert, mock_get_pool
    ):
        """Editing to shorter content (negative delta) should skip char cap check."""
        msg_row = _make_message_row(
            sender_id=_SENDER_ID, content="A very long message", created_at=_NOW
        )
        updated_row = _make_message_row(sender_id=_SENDER_ID, content="Short", is_edited=True)
        conv = _make_conversation(
            conv_id=msg_row["conversation_id"],
            user_a=_SENDER_ID,
            user_b=_RECIPIENT_ID,
        )

        pool, conn = _mock_pool_conn()

        fetchval_calls = []

        async def mock_fetchval(*args, **kwargs):
            sql = args[0] if args else ""
            fetchval_calls.append(sql)
            if "pg_advisory_xact_lock" in sql:
                return None
            return None

        conn.fetchrow = AsyncMock(side_effect=[msg_row, updated_row])
        conn.fetchval = AsyncMock(side_effect=mock_fetchval)
        mock_get_pool.return_value = pool

        mock_dm_repo.find_conversation_by_id = AsyncMock(return_value=conv)
        mock_convert.return_value = {
            "id": str(_MSG_ID),
            "conversation_id": str(_CONV_ID),
            "sender": {"id": _SENDER_ID, "display_name": "Test", "avatar_url": None},
            "content": "Short",
            "attachment_url": None,
            "attachment_name": None,
            "attachment_size": None,
            "attachment_expires_at": None,
            "is_recalled": False,
            "is_edited": True,
            "read_at": None,
            "created_at": _NOW.isoformat(),
            "updated_at": _NOW.isoformat(),
        }

        from app.services.dm import edit_message

        result = await edit_message(str(_MSG_ID), _SENDER_ID, "Short")
        assert result is not None
        # No total_chars query should have been made (only advisory lock)
        total_chars_queries = [s for s in fetchval_calls if "total_chars" in s]
        assert len(total_chars_queries) == 0, "Shrinking edit should skip char cap check"


# ===========================================================================
# H-07: WS failure blocks DB notification
# ===========================================================================


class TestH07WSFailureNotification:
    """H-07: WS failure should not prevent DB notification creation."""

    @pytest.mark.anyio
    async def test_db_notification_created_when_ws_fails(self):
        """DB notification is created even when send_to_user raises."""
        from app.event_handlers import _on_dm_message_sent

        sender_id = str(uuid.uuid4())
        recipient_id = str(uuid.uuid4())
        conv_id = str(uuid.uuid4())

        message = {
            "id": str(uuid.uuid4()),
            "conversation_id": conv_id,
            "sender": {"id": sender_id, "display_name": "Alice", "avatar_url": None},
            "content": "Hello!",
        }

        mock_create_notification = AsyncMock()

        with (
            patch(
                "app.api.v1.endpoints.ws.send_to_user",
                new_callable=AsyncMock,
                side_effect=ConnectionError("WebSocket connection failed"),
            ),
            patch(
                "app.event_handlers._check_idempotent",
                new_callable=AsyncMock,
                return_value=True,
            ),
            patch(
                "app.services.notification.create_notification",
                mock_create_notification,
            ),
        ):
            # Should NOT raise despite WS failure
            await _on_dm_message_sent(
                recipient_id=recipient_id,
                message=message,
                sender_id=sender_id,
            )

        # DB notification should have been created
        mock_create_notification.assert_awaited_once()
        call_kwargs = mock_create_notification.call_args.kwargs
        assert call_kwargs["user_id"] == recipient_id
        assert call_kwargs["action_type"] == "NEW_DM"

    @pytest.mark.anyio
    async def test_ws_success_also_creates_notification(self):
        """When WS succeeds, DB notification is still created."""
        from app.event_handlers import _on_dm_message_sent

        sender_id = str(uuid.uuid4())
        recipient_id = str(uuid.uuid4())
        conv_id = str(uuid.uuid4())

        message = {
            "id": str(uuid.uuid4()),
            "conversation_id": conv_id,
            "sender": {"id": sender_id, "display_name": "Alice", "avatar_url": None},
            "content": "Hello!",
        }

        mock_create_notification = AsyncMock()

        with (
            patch(
                "app.api.v1.endpoints.ws.send_to_user",
                new_callable=AsyncMock,
            ),
            patch(
                "app.event_handlers._check_idempotent",
                new_callable=AsyncMock,
                return_value=True,
            ),
            patch(
                "app.services.notification.create_notification",
                mock_create_notification,
            ),
        ):
            await _on_dm_message_sent(
                recipient_id=recipient_id,
                message=message,
                sender_id=sender_id,
            )

        mock_create_notification.assert_awaited_once()


# ===========================================================================
# H-08: Conversation list attachment_key always null
# ===========================================================================


class TestH08ConversationAttachmentKey:
    """H-08: async_row_to_conversation must include attachment_key."""

    @pytest.mark.anyio
    async def test_attachment_key_present_in_conversation(self):
        """Converted conversation includes last_msg attachment_key."""
        from app.converters.dm_converter import async_row_to_conversation

        user_id = str(uuid.uuid4())
        other_id = str(uuid.uuid4())
        attachment_key = "dm/user123/abc123.pdf"

        row = {
            "id": uuid.uuid4(),
            "participant_a": uuid.UUID(user_id),
            "participant_b": uuid.UUID(other_id),
            "total_chars": 100,
            "updated_at": _NOW,
            "other_user_id": uuid.UUID(other_id),
            "other_display_name": "Bob",
            "other_avatar_url": None,
            "last_msg_id": uuid.uuid4(),
            "last_msg_conversation_id": uuid.uuid4(),
            "last_msg_sender_id": uuid.UUID(user_id),
            "last_msg_content": "Check this file",
            "last_msg_attachment_key": attachment_key,
            "last_msg_attachment_name": "report.pdf",
            "last_msg_attachment_size": 2048,
            "last_msg_attachment_expires_at": _NOW + timedelta(days=3),
            "last_msg_is_recalled": False,
            "last_msg_is_edited": False,
            "last_msg_read_at": None,
            "last_msg_created_at": _NOW,
            "last_msg_updated_at": _NOW,
            "last_msg_sender_display_name": "Alice",
            "last_msg_sender_avatar_url": None,
            "unread_count": 1,
        }

        with patch(
            "app.converters.dm_converter.async_resolve_avatar_url",
            new_callable=AsyncMock,
            return_value=None,
        ):
            result = await async_row_to_conversation(row, user_id)

        last_msg = result["last_message"]
        assert last_msg is not None
        assert "attachment_key" in last_msg
        assert last_msg["attachment_key"] == attachment_key

    @pytest.mark.anyio
    async def test_attachment_key_none_when_no_attachment(self):
        """Converted conversation has None attachment_key when no attachment."""
        from app.converters.dm_converter import async_row_to_conversation

        user_id = str(uuid.uuid4())
        other_id = str(uuid.uuid4())

        row = {
            "id": uuid.uuid4(),
            "participant_a": uuid.UUID(user_id),
            "participant_b": uuid.UUID(other_id),
            "total_chars": 100,
            "updated_at": _NOW,
            "other_user_id": uuid.UUID(other_id),
            "other_display_name": "Bob",
            "other_avatar_url": None,
            "last_msg_id": uuid.uuid4(),
            "last_msg_conversation_id": uuid.uuid4(),
            "last_msg_sender_id": uuid.UUID(user_id),
            "last_msg_content": "Hello",
            "last_msg_attachment_key": None,
            "last_msg_attachment_name": None,
            "last_msg_attachment_size": None,
            "last_msg_attachment_expires_at": None,
            "last_msg_is_recalled": False,
            "last_msg_is_edited": False,
            "last_msg_read_at": None,
            "last_msg_created_at": _NOW,
            "last_msg_updated_at": _NOW,
            "last_msg_sender_display_name": "Alice",
            "last_msg_sender_avatar_url": None,
            "unread_count": 0,
        }

        with patch(
            "app.converters.dm_converter.async_resolve_avatar_url",
            new_callable=AsyncMock,
            return_value=None,
        ):
            result = await async_row_to_conversation(row, user_id)

        last_msg = result["last_message"]
        assert last_msg is not None
        assert last_msg["attachment_key"] is None


# ===========================================================================
# M-05: Friendship check re-verified inside send_message_atomic
# ===========================================================================


class TestM05FriendshipCheckInTransaction:
    """M-05: dm_friends_only re-checked inside send_message_atomic transaction."""

    def test_send_message_atomic_source_checks_dm_friends_only(self):
        """Verify source code of send_message_atomic includes dm_friends_only check."""
        import inspect

        from app.repositories import dm_repo

        source = inspect.getsource(dm_repo.send_message_atomic)
        assert "dm_friends_only" in source, (
            "send_message_atomic must re-check dm_friends_only inside transaction"
        )
        assert "friendships" in source, (
            "send_message_atomic must check friendships table inside transaction"
        )

    def test_send_message_atomic_checks_friends_before_insert(self):
        """dm_friends_only check must appear before INSERT in the source."""
        import inspect

        from app.repositories import dm_repo

        source = inspect.getsource(dm_repo.send_message_atomic)
        friends_pos = source.index("dm_friends_only")
        insert_pos = source.index("INSERT INTO dm_messages")
        assert friends_pos < insert_pos, (
            "dm_friends_only check must happen before INSERT"
        )


# ===========================================================================
# M-18: DM text cleanup uses advisory lock
# ===========================================================================


class TestM18CleanupAdvisoryLock:
    """M-18: _cleanup_text uses pg_advisory_xact_lock to prevent double-decrement."""

    def test_cleanup_text_source_has_advisory_lock(self):
        """Verify _cleanup_text source code includes advisory lock."""
        # Need to set up celery mocks before import
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

        try:
            # Force reimport
            if "app.tasks.dm_cleanup" in sys.modules:
                del sys.modules["app.tasks.dm_cleanup"]

            import importlib
            import inspect

            mod = importlib.import_module("app.tasks.dm_cleanup")
            source = inspect.getsource(mod._cleanup_text)
            assert "pg_advisory_xact_lock" in source, (
                "_cleanup_text must use pg_advisory_xact_lock to prevent race condition"
            )
        finally:
            for key, val in saved.items():
                if val is None:
                    sys.modules.pop(key, None)
                else:
                    sys.modules[key] = val
            sys.modules.pop("app.tasks.dm_cleanup", None)


# ===========================================================================
# M-19: Recalled message content stripped by converter
# ===========================================================================


class TestM19RecalledMessageContent:
    """M-19: Converter must strip content from recalled messages."""

    @pytest.mark.anyio
    async def test_recalled_message_content_is_none(self):
        """Recalled message should have content=None regardless of DB value."""
        from app.converters.dm_converter import async_row_to_message

        row = _make_message_row(
            content="This should be hidden",
            is_recalled=True,
            attachment_name="secret.pdf",
            attachment_size=1024,
            attachment_expires_at=_NOW + timedelta(days=3),
        )

        with patch(
            "app.converters.dm_converter.async_resolve_avatar_url",
            new_callable=AsyncMock,
            return_value=None,
        ):
            result = await async_row_to_message(row)

        assert result["is_recalled"] is True
        assert result["content"] is None
        assert result["attachment_name"] is None
        assert result["attachment_size"] is None
        assert result["attachment_expires_at"] is None

    @pytest.mark.anyio
    async def test_non_recalled_message_preserves_content(self):
        """Non-recalled message should preserve content."""
        from app.converters.dm_converter import async_row_to_message

        row = _make_message_row(
            content="Normal message",
            is_recalled=False,
            attachment_name="file.pdf",
            attachment_size=2048,
            attachment_expires_at=_NOW + timedelta(days=3),
        )

        with patch(
            "app.converters.dm_converter.async_resolve_avatar_url",
            new_callable=AsyncMock,
            return_value=None,
        ):
            result = await async_row_to_message(row)

        assert result["is_recalled"] is False
        assert result["content"] == "Normal message"
        assert result["attachment_name"] == "file.pdf"
        assert result["attachment_size"] == 2048
        assert result["attachment_expires_at"] is not None


# ===========================================================================
# M-24: _DEFAULTS includes dm_friends_only
# ===========================================================================


class TestM24DefaultsDmFriendsOnly:
    """M-24: preferences _DEFAULTS must include dm_friends_only."""

    def test_dm_friends_only_in_defaults(self):
        """_DEFAULTS dict should contain dm_friends_only: False."""
        from app.services.preferences import _DEFAULTS

        assert "dm_friends_only" in _DEFAULTS
        assert _DEFAULTS["dm_friends_only"] is False

    @pytest.mark.anyio
    async def test_get_preferences_returns_dm_friends_only_default(self):
        """When no row exists, get_user_preferences returns dm_friends_only default."""
        with patch(
            "app.repositories.preferences_repo.get_preferences",
            new_callable=AsyncMock,
            return_value=None,
        ):
            from app.services.preferences import get_user_preferences

            result = await get_user_preferences(uuid.uuid4())

        assert "dm_friends_only" in result
        assert result["dm_friends_only"] is False


# ===========================================================================
# L-12: Orphan file cleaner for dm/ prefix
# ===========================================================================


class TestL12DmOrphanFileCleaner:
    """L-12: cleanup_dm_orphan_files task detects and removes orphan dm/ files."""

    def test_orphan_cleanup_task_exists(self):
        """Verify cleanup_dm_orphan_files function exists in dm_cleanup module."""
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

        try:
            if "app.tasks.dm_cleanup" in sys.modules:
                del sys.modules["app.tasks.dm_cleanup"]

            import importlib

            mod = importlib.import_module("app.tasks.dm_cleanup")
            assert hasattr(mod, "cleanup_dm_orphan_files")
            assert hasattr(mod, "_cleanup_dm_orphans")
            assert hasattr(mod, "_process_dm_orphan_batch")
        finally:
            for key, val in saved.items():
                if val is None:
                    sys.modules.pop(key, None)
                else:
                    sys.modules[key] = val
            sys.modules.pop("app.tasks.dm_cleanup", None)

    @pytest.mark.anyio
    async def test_orphan_batch_detects_unreferenced_files(self):
        """_process_dm_orphan_batch deletes keys not in dm_messages."""
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

        try:
            if "app.tasks.dm_cleanup" in sys.modules:
                del sys.modules["app.tasks.dm_cleanup"]

            import importlib

            mod = importlib.import_module("app.tasks.dm_cleanup")

            keys = [
                "dm/user1/abc.pdf",  # referenced
                "dm/user1/def.pdf",  # orphan
                "dm/user2/ghi.jpg",  # orphan
            ]

            # Only the first key is referenced
            mock_conn = MagicMock()
            mock_conn.fetch = AsyncMock(
                return_value=[{"attachment_key": "dm/user1/abc.pdf"}]
            )
            mock_acq = MagicMock()
            mock_acq.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_acq.__aexit__ = AsyncMock(return_value=None)
            mock_pool = MagicMock()
            mock_pool.acquire.return_value = mock_acq

            mock_client = MagicMock()
            mock_client.delete_object = MagicMock()

            deleted, errors = await mod._process_dm_orphan_batch(
                mock_pool, mock_client, "test-bucket", keys
            )

            assert deleted == 2  # 2 orphans deleted
            assert errors == 0
            assert mock_client.delete_object.call_count == 2

            # Check the correct keys were deleted
            deleted_keys = {
                call.kwargs["Key"]
                for call in mock_client.delete_object.call_args_list
            }
            assert deleted_keys == {"dm/user1/def.pdf", "dm/user2/ghi.jpg"}
        finally:
            for key, val in saved.items():
                if val is None:
                    sys.modules.pop(key, None)
                else:
                    sys.modules[key] = val
            sys.modules.pop("app.tasks.dm_cleanup", None)

    @pytest.mark.anyio
    async def test_orphan_batch_all_referenced(self):
        """No deletions when all files are referenced."""
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

        try:
            if "app.tasks.dm_cleanup" in sys.modules:
                del sys.modules["app.tasks.dm_cleanup"]

            import importlib

            mod = importlib.import_module("app.tasks.dm_cleanup")

            keys = ["dm/user1/abc.pdf", "dm/user1/def.pdf"]

            mock_conn = MagicMock()
            mock_conn.fetch = AsyncMock(
                return_value=[
                    {"attachment_key": "dm/user1/abc.pdf"},
                    {"attachment_key": "dm/user1/def.pdf"},
                ]
            )
            mock_acq = MagicMock()
            mock_acq.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_acq.__aexit__ = AsyncMock(return_value=None)
            mock_pool = MagicMock()
            mock_pool.acquire.return_value = mock_acq

            mock_client = MagicMock()

            deleted, errors = await mod._process_dm_orphan_batch(
                mock_pool, mock_client, "test-bucket", keys
            )

            assert deleted == 0
            assert errors == 0
            mock_client.delete_object.assert_not_called()
        finally:
            for key, val in saved.items():
                if val is None:
                    sys.modules.pop(key, None)
                else:
                    sys.modules[key] = val
            sys.modules.pop("app.tasks.dm_cleanup", None)


# ===========================================================================
# L-16: DM attachment filename sanitization
# ===========================================================================


class TestL16FilenameSanitization:
    """L-16: DM endpoint sanitizes filenames before storing."""

    def test_sanitize_strips_path_separators(self):
        """os.path.basename strips directory components."""
        raw = "../../etc/passwd"
        sanitized = os.path.basename(raw).replace("..", "")
        assert "/" not in sanitized
        assert "\\" not in sanitized
        assert sanitized == "passwd"

    def test_sanitize_strips_double_dots(self):
        """Double dots are removed."""
        raw = "..file..name..txt"
        sanitized = os.path.basename(raw).replace("..", "")
        assert ".." not in sanitized

    def test_sanitize_strips_control_characters(self):
        """Control characters are removed."""
        raw = "file\x00name\x1f.txt"
        sanitized = re.sub(r"[\x00-\x1f\x7f]", "", raw)
        assert "\x00" not in sanitized
        assert "\x1f" not in sanitized

    def test_sanitize_limits_length(self):
        """Filename is limited to 255 chars."""
        raw = "a" * 300 + ".pdf"
        if len(raw) > 255:
            base, ext = os.path.splitext(raw)
            raw = base[: 255 - len(ext)] + ext
        assert len(raw) <= 255
        assert raw.endswith(".pdf")

    def test_sanitize_empty_result_becomes_attachment(self):
        """If sanitization empties the name, it becomes 'attachment'."""
        raw = "\x00\x01\x02"
        sanitized = os.path.basename(raw).replace("..", "")
        sanitized = re.sub(r"[\x00-\x1f\x7f]", "", sanitized)
        file_name = sanitized or "attachment"
        assert file_name == "attachment"

    def test_sanitize_preserves_normal_filename(self):
        """Normal filenames pass through unchanged."""
        raw = "report_2024.pdf"
        sanitized = os.path.basename(raw).replace("..", "")
        sanitized = re.sub(r"[\x00-\x1f\x7f]", "", sanitized)
        if len(sanitized) > 255:
            base, ext = os.path.splitext(sanitized)
            sanitized = base[: 255 - len(ext)] + ext
        assert sanitized == "report_2024.pdf"

    def test_endpoint_source_has_sanitization(self):
        """Verify the endpoint source code includes filename sanitization."""
        import inspect

        from app.api.v1.endpoints import dm

        source = inspect.getsource(dm.send_message)
        assert "os.path.basename" in source, "Endpoint must use os.path.basename"
        assert "replace('..'," in source or 'replace("..",' in source, (
            "Endpoint must strip double dots"
        )
        assert "255" in source, "Endpoint must limit filename to 255 chars"
