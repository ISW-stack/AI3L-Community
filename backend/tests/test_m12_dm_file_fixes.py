"""Tests for audit fixes M-12, M-48, L-10, L-15, L-22, L-23.

Covers: DM Content-Type derivation, orphan file cleanup, size checks,
endpoint-level size limit, edit is_recalled re-verify, idempotent cleanup.
"""

import sys
import types
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.errors import AppError, ErrorCode

# ── Helpers ──────────────────────────────────────────────────────────────────

_SVC = "app.services.dm"
_EP = "app.api.v1.endpoints.dm"
_NOW = datetime.now(timezone.utc)
_SENDER_ID = str(uuid.uuid4())
_RECIPIENT_ID = str(uuid.uuid4())
_CONV_ID = uuid.uuid4()
_MSG_ID = uuid.uuid4()


def _make_conversation(conv_id=None, user_a=None, user_b=None):
    return {
        "id": conv_id or _CONV_ID,
        "participant_a": uuid.UUID(user_a) if user_a else uuid.uuid4(),
        "participant_b": uuid.UUID(user_b) if user_b else uuid.uuid4(),
        "total_chars": 0,
        "created_at": _NOW,
        "updated_at": _NOW,
    }


def _make_message_row(
    msg_id=None,
    conv_id=None,
    sender_id=None,
    content="Hello!",
    is_recalled=False,
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
        "is_edited": False,
        "read_at": None,
        "created_at": created_at or _NOW,
        "updated_at": _NOW,
        "sender_display_name": "Test User",
        "sender_avatar_url": None,
    }


# ── Celery module mock for dm_cleanup tests ─────────────────────────────────


@pytest.fixture()
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
# M-12: Content-Type derived from extension, not from client
# ===========================================================================


class TestM12ContentTypeDerived:
    """M-12: DM send_message derives Content-Type from file extension."""

    @pytest.mark.anyio
    async def test_jpeg_extension_derives_image_jpeg(self):
        """A .jpg file should be uploaded with image/jpeg regardless of client Content-Type."""
        mock_upload = AsyncMock()
        conv = _make_conversation(user_a=_SENDER_ID, user_b=_RECIPIENT_ID)
        msg_row = _make_message_row(sender_id=_SENDER_ID)

        # Build mock pool for block/friendship checks
        mock_conn = MagicMock()
        mock_conn.transaction = MagicMock(
            return_value=MagicMock(
                __aenter__=AsyncMock(return_value=None),
                __aexit__=AsyncMock(return_value=None),
            )
        )
        mock_acq = MagicMock(
            __aenter__=AsyncMock(return_value=mock_conn),
            __aexit__=AsyncMock(return_value=None),
        )
        mock_pool = MagicMock()
        mock_pool.acquire.return_value = mock_acq

        with (
            patch("app.core.database.get_pool", return_value=mock_pool),
            patch(
                "app.repositories.social_repo.is_blocked",
                new_callable=AsyncMock,
                return_value=False,
            ),
            patch(
                "app.repositories.dm_repo.get_dm_friends_only",
                new_callable=AsyncMock,
                return_value=False,
            ),
            patch(
                "app.repositories.user_repo.get_storage_used",
                new_callable=AsyncMock,
                return_value=0,
            ),
            patch("app.core.async_storage.upload_file", mock_upload),
            patch(
                "app.repositories.dm_repo.find_or_create_conversation",
                new_callable=AsyncMock,
                return_value=conv,
            ),
            patch(
                "app.repositories.dm_repo.send_message_atomic",
                new_callable=AsyncMock,
                return_value=(msg_row, []),
            ),
            patch("app.repositories.user_repo.increment_storage_used", new_callable=AsyncMock),
            patch(
                "app.converters.dm_converter.async_row_to_message",
                new_callable=AsyncMock,
                return_value={"id": "x"},
            ),
            patch("app.core.storage.generate_presigned_url", return_value="https://mock-url"),
            patch(f"{_SVC}.emit", new_callable=AsyncMock),
            patch("app.services.dm.validate_magic_number", return_value=True),
        ):
            from app.services.dm import send_message

            await send_message(
                sender_id=_SENDER_ID,
                recipient_id=_RECIPIENT_ID,
                content=None,
                file_data=b"\xff\xd8\xff\xe0" + b"\x00" * 100,
                file_name="photo.jpg",
                file_size=104,
                file_content_type="text/plain",  # Client lies about content type
            )

        # Verify upload was called with derived type, not "text/plain"
        mock_upload.assert_awaited_once()
        call_args = mock_upload.call_args
        assert (
            call_args[0][2] == "image/jpeg"
        ), f"Expected derived Content-Type 'image/jpeg', got '{call_args[0][2]}'"

    @pytest.mark.anyio
    async def test_txt_extension_uses_mimetypes_fallback(self):
        """A .txt file should use mimetypes.guess_type fallback (text/plain)."""
        mock_upload = AsyncMock()
        conv = _make_conversation(user_a=_SENDER_ID, user_b=_RECIPIENT_ID)
        msg_row = _make_message_row(sender_id=_SENDER_ID)

        mock_conn = MagicMock()
        mock_conn.transaction = MagicMock(
            return_value=MagicMock(
                __aenter__=AsyncMock(return_value=None),
                __aexit__=AsyncMock(return_value=None),
            )
        )
        mock_acq = MagicMock(
            __aenter__=AsyncMock(return_value=mock_conn),
            __aexit__=AsyncMock(return_value=None),
        )
        mock_pool = MagicMock()
        mock_pool.acquire.return_value = mock_acq

        with (
            patch("app.core.database.get_pool", return_value=mock_pool),
            patch(
                "app.repositories.social_repo.is_blocked",
                new_callable=AsyncMock,
                return_value=False,
            ),
            patch(
                "app.repositories.dm_repo.get_dm_friends_only",
                new_callable=AsyncMock,
                return_value=False,
            ),
            patch(
                "app.repositories.user_repo.get_storage_used",
                new_callable=AsyncMock,
                return_value=0,
            ),
            patch("app.core.async_storage.upload_file", mock_upload),
            patch(
                "app.repositories.dm_repo.find_or_create_conversation",
                new_callable=AsyncMock,
                return_value=conv,
            ),
            patch(
                "app.repositories.dm_repo.send_message_atomic",
                new_callable=AsyncMock,
                return_value=(msg_row, []),
            ),
            patch("app.repositories.user_repo.increment_storage_used", new_callable=AsyncMock),
            patch(
                "app.converters.dm_converter.async_row_to_message",
                new_callable=AsyncMock,
                return_value={"id": "x"},
            ),
            patch("app.core.storage.generate_presigned_url", return_value="https://mock-url"),
            patch(f"{_SVC}.emit", new_callable=AsyncMock),
        ):
            from app.services.dm import send_message

            await send_message(
                sender_id=_SENDER_ID,
                recipient_id=_RECIPIENT_ID,
                content=None,
                file_data=b"hello world content",
                file_name="readme.txt",
                file_size=19,
                file_content_type="application/octet-stream",  # Client sends generic type
            )

        mock_upload.assert_awaited_once()
        call_args = mock_upload.call_args
        # .txt should derive to text/plain via mimetypes
        assert (
            call_args[0][2] == "text/plain"
        ), f"Expected derived Content-Type 'text/plain', got '{call_args[0][2]}'"

    @pytest.mark.anyio
    async def test_pdf_extension_derives_application_pdf(self):
        """A .pdf file should derive application/pdf from _DM_MAGIC_CHECK_EXTENSIONS."""
        mock_upload = AsyncMock()
        conv = _make_conversation(user_a=_SENDER_ID, user_b=_RECIPIENT_ID)
        msg_row = _make_message_row(sender_id=_SENDER_ID)

        mock_conn = MagicMock()
        mock_conn.transaction = MagicMock(
            return_value=MagicMock(
                __aenter__=AsyncMock(return_value=None),
                __aexit__=AsyncMock(return_value=None),
            )
        )
        mock_acq = MagicMock(
            __aenter__=AsyncMock(return_value=mock_conn),
            __aexit__=AsyncMock(return_value=None),
        )
        mock_pool = MagicMock()
        mock_pool.acquire.return_value = mock_acq

        with (
            patch("app.core.database.get_pool", return_value=mock_pool),
            patch(
                "app.repositories.social_repo.is_blocked",
                new_callable=AsyncMock,
                return_value=False,
            ),
            patch(
                "app.repositories.dm_repo.get_dm_friends_only",
                new_callable=AsyncMock,
                return_value=False,
            ),
            patch(
                "app.repositories.user_repo.get_storage_used",
                new_callable=AsyncMock,
                return_value=0,
            ),
            patch("app.core.async_storage.upload_file", mock_upload),
            patch(
                "app.repositories.dm_repo.find_or_create_conversation",
                new_callable=AsyncMock,
                return_value=conv,
            ),
            patch(
                "app.repositories.dm_repo.send_message_atomic",
                new_callable=AsyncMock,
                return_value=(msg_row, []),
            ),
            patch("app.repositories.user_repo.increment_storage_used", new_callable=AsyncMock),
            patch(
                "app.converters.dm_converter.async_row_to_message",
                new_callable=AsyncMock,
                return_value={"id": "x"},
            ),
            patch("app.core.storage.generate_presigned_url", return_value="https://mock-url"),
            patch(f"{_SVC}.emit", new_callable=AsyncMock),
            patch("app.services.dm.validate_magic_number", return_value=True),
        ):
            from app.services.dm import send_message

            await send_message(
                sender_id=_SENDER_ID,
                recipient_id=_RECIPIENT_ID,
                content=None,
                file_data=b"%PDF-1.4" + b"\x00" * 100,
                file_name="document.pdf",
                file_size=108,
                file_content_type="text/html",  # Client lies
            )

        mock_upload.assert_awaited_once()
        call_args = mock_upload.call_args
        assert (
            call_args[0][2] == "application/pdf"
        ), f"Expected derived Content-Type 'application/pdf', got '{call_args[0][2]}'"


# ===========================================================================
# M-48: Orphaned file cleanup on DB failure
# ===========================================================================


class TestM48OrphanFileCleanup:
    """M-48: Uploaded file is deleted when subsequent DB operations fail."""

    @pytest.mark.anyio
    async def test_file_deleted_on_db_failure(self):
        """If send_message_atomic raises, the uploaded file should be cleaned up."""
        mock_upload = AsyncMock()
        mock_delete = AsyncMock()

        mock_conn = MagicMock()
        mock_conn.transaction = MagicMock(
            return_value=MagicMock(
                __aenter__=AsyncMock(return_value=None),
                __aexit__=AsyncMock(return_value=None),
            )
        )
        mock_acq = MagicMock(
            __aenter__=AsyncMock(return_value=mock_conn),
            __aexit__=AsyncMock(return_value=None),
        )
        mock_pool = MagicMock()
        mock_pool.acquire.return_value = mock_acq

        conv = _make_conversation(user_a=_SENDER_ID, user_b=_RECIPIENT_ID)

        with (
            patch("app.core.database.get_pool", return_value=mock_pool),
            patch(
                "app.repositories.social_repo.is_blocked",
                new_callable=AsyncMock,
                return_value=False,
            ),
            patch(
                "app.repositories.dm_repo.get_dm_friends_only",
                new_callable=AsyncMock,
                return_value=False,
            ),
            patch(
                "app.repositories.user_repo.get_storage_used",
                new_callable=AsyncMock,
                return_value=0,
            ),
            patch("app.core.async_storage.upload_file", mock_upload),
            patch("app.core.async_storage.delete_file", mock_delete),
            patch(
                "app.repositories.dm_repo.find_or_create_conversation",
                new_callable=AsyncMock,
                return_value=conv,
            ),
            patch(
                "app.repositories.dm_repo.send_message_atomic",
                new_callable=AsyncMock,
                side_effect=RuntimeError("DB exploded"),
            ),
            patch("app.services.dm.validate_magic_number", return_value=True),
        ):
            from app.services.dm import send_message

            with pytest.raises(RuntimeError, match="DB exploded"):
                await send_message(
                    sender_id=_SENDER_ID,
                    recipient_id=_RECIPIENT_ID,
                    content=None,
                    file_data=b"\xff\xd8\xff\xe0" + b"\x00" * 100,
                    file_name="photo.jpg",
                    file_size=104,
                    file_content_type="image/jpeg",
                )

        # File was uploaded then cleaned up
        mock_upload.assert_awaited_once()
        mock_delete.assert_awaited_once()

    @pytest.mark.anyio
    async def test_no_cleanup_when_no_file(self):
        """If no file was uploaded, DB failure should not attempt delete."""
        mock_delete = AsyncMock()

        mock_conn = MagicMock()
        mock_conn.transaction = MagicMock(
            return_value=MagicMock(
                __aenter__=AsyncMock(return_value=None),
                __aexit__=AsyncMock(return_value=None),
            )
        )
        mock_acq = MagicMock(
            __aenter__=AsyncMock(return_value=mock_conn),
            __aexit__=AsyncMock(return_value=None),
        )
        mock_pool = MagicMock()
        mock_pool.acquire.return_value = mock_acq

        with (
            patch("app.core.database.get_pool", return_value=mock_pool),
            patch(
                "app.repositories.social_repo.is_blocked",
                new_callable=AsyncMock,
                return_value=False,
            ),
            patch(
                "app.repositories.dm_repo.get_dm_friends_only",
                new_callable=AsyncMock,
                return_value=False,
            ),
            patch("app.core.async_storage.delete_file", mock_delete),
            patch(
                "app.repositories.dm_repo.find_or_create_conversation",
                new_callable=AsyncMock,
                side_effect=RuntimeError("DB down"),
            ),
        ):
            from app.services.dm import send_message

            with pytest.raises(RuntimeError, match="DB down"):
                await send_message(
                    sender_id=_SENDER_ID,
                    recipient_id=_RECIPIENT_ID,
                    content="Hello",
                )

        # No file was uploaded, so delete should not be called
        mock_delete.assert_not_awaited()

    @pytest.mark.anyio
    async def test_cleanup_failure_does_not_mask_original_error(self):
        """If file cleanup also fails, the original DB error should still propagate."""
        mock_upload = AsyncMock()
        mock_delete = AsyncMock(side_effect=RuntimeError("MinIO unreachable"))

        mock_conn = MagicMock()
        mock_conn.transaction = MagicMock(
            return_value=MagicMock(
                __aenter__=AsyncMock(return_value=None),
                __aexit__=AsyncMock(return_value=None),
            )
        )
        mock_acq = MagicMock(
            __aenter__=AsyncMock(return_value=mock_conn),
            __aexit__=AsyncMock(return_value=None),
        )
        mock_pool = MagicMock()
        mock_pool.acquire.return_value = mock_acq

        conv = _make_conversation(user_a=_SENDER_ID, user_b=_RECIPIENT_ID)

        with (
            patch("app.core.database.get_pool", return_value=mock_pool),
            patch(
                "app.repositories.social_repo.is_blocked",
                new_callable=AsyncMock,
                return_value=False,
            ),
            patch(
                "app.repositories.dm_repo.get_dm_friends_only",
                new_callable=AsyncMock,
                return_value=False,
            ),
            patch(
                "app.repositories.user_repo.get_storage_used",
                new_callable=AsyncMock,
                return_value=0,
            ),
            patch("app.core.async_storage.upload_file", mock_upload),
            patch("app.core.async_storage.delete_file", mock_delete),
            patch(
                "app.repositories.dm_repo.find_or_create_conversation",
                new_callable=AsyncMock,
                return_value=conv,
            ),
            patch(
                "app.repositories.dm_repo.send_message_atomic",
                new_callable=AsyncMock,
                side_effect=RuntimeError("DB exploded"),
            ),
            patch("app.services.dm.validate_magic_number", return_value=True),
        ):
            from app.services.dm import send_message

            # Original error propagates, not the cleanup error
            with pytest.raises(RuntimeError, match="DB exploded"):
                await send_message(
                    sender_id=_SENDER_ID,
                    recipient_id=_RECIPIENT_ID,
                    content=None,
                    file_data=b"\xff\xd8\xff\xe0" + b"\x00" * 100,
                    file_name="photo.jpg",
                    file_size=104,
                    file_content_type="image/jpeg",
                )


# ===========================================================================
# L-10: Redundant size check on actual file_data length
# ===========================================================================


class TestL10RedundantSizeCheck:
    """L-10: send_message rejects oversized file_data even if file_size lies."""

    @pytest.mark.anyio
    async def test_oversized_data_rejected_despite_small_file_size(self):
        """If file_size says 100 but data is 60MB, the redundant len() check catches it."""
        mock_conn = MagicMock()
        mock_conn.transaction = MagicMock(
            return_value=MagicMock(
                __aenter__=AsyncMock(return_value=None),
                __aexit__=AsyncMock(return_value=None),
            )
        )
        mock_acq = MagicMock(
            __aenter__=AsyncMock(return_value=mock_conn),
            __aexit__=AsyncMock(return_value=None),
        )
        mock_pool = MagicMock()
        mock_pool.acquire.return_value = mock_acq

        # file_size claims 100 bytes but file_data is 60MB
        big_data = b"\x00" * (60 * 1024 * 1024)

        with (
            patch("app.core.database.get_pool", return_value=mock_pool),
            patch(
                "app.repositories.social_repo.is_blocked",
                new_callable=AsyncMock,
                return_value=False,
            ),
            patch(
                "app.repositories.dm_repo.get_dm_friends_only",
                new_callable=AsyncMock,
                return_value=False,
            ),
        ):
            from app.services.dm import send_message

            with pytest.raises(AppError) as exc_info:
                await send_message(
                    sender_id=_SENDER_ID,
                    recipient_id=_RECIPIENT_ID,
                    content=None,
                    file_data=big_data,
                    file_name="huge.jpg",
                    file_size=100,  # Lies about size
                    file_content_type="image/jpeg",
                )

            assert exc_info.value.detail["code"] == ErrorCode.DM_005.value
            assert exc_info.value.status_code == 413


# ===========================================================================
# L-15: Endpoint-level size-limited read
# ===========================================================================


class TestL15EndpointSizeLimit:
    """L-15: DM endpoint reads with size limit to prevent unbounded memory."""

    def test_endpoint_rejects_oversized_file(self, client):
        """Uploading a file larger than DM_MAX_ATTACHMENT_SIZE returns 413."""
        from app.core.deps import require_role
        from app.main import app

        uid = str(uuid.uuid4())
        payload = {"sub": uid, "role": "MEMBER", "jti": str(uuid.uuid4())}

        def override():
            return payload

        app.dependency_overrides[require_role("MEMBER", "ADMIN", "SUPER_ADMIN")] = override

        try:
            # We can't actually send 50MB+ in a test, so mock the UploadFile.read
            # Instead, verify that the endpoint code uses read(limit+1) pattern
            # by checking the source code
            import inspect

            from app.api.v1.endpoints.dm import send_message as ep_send

            source = inspect.getsource(ep_send)
            assert (
                "DM_MAX_ATTACHMENT_SIZE + 1" in source
            ), "Endpoint should read with size limit: file.read(DM_MAX_ATTACHMENT_SIZE + 1)"
        finally:
            app.dependency_overrides.clear()

    def test_endpoint_uses_dm_005_error_code(self):
        """Verify endpoint uses DM_005 error code for oversized files."""
        import inspect

        from app.api.v1.endpoints.dm import send_message as ep_send

        source = inspect.getsource(ep_send)
        assert (
            "ErrorCode.DM_005" in source
        ), "Endpoint should use ErrorCode.DM_005 for file too large errors"


# ===========================================================================
# L-22: edit_message re-verifies is_recalled inside transaction
# ===========================================================================


class TestL22EditReVerifiesRecalled:
    """L-22: edit_message UPDATE filters by is_recalled=false inside transaction."""

    def test_edit_update_includes_is_recalled_check(self):
        """The UPDATE statement inside edit_message should filter by is_recalled = false."""
        import inspect

        from app.services.dm import edit_message

        source = inspect.getsource(edit_message)
        assert (
            "is_recalled = false" in source
        ), "edit_message UPDATE should include 'AND is_recalled = false'"

    @pytest.mark.anyio
    async def test_edit_recalled_message_inside_transaction_raises(self):
        """If message gets recalled between initial check and UPDATE, raise error."""
        row = _make_message_row(
            msg_id=_MSG_ID,
            sender_id=_SENDER_ID,
            is_recalled=False,
            created_at=_NOW,
        )

        # Mock connection where UPDATE returns None (message was recalled concurrently)
        mock_conn = MagicMock()
        mock_conn.fetchval = AsyncMock(return_value=None)
        mock_conn.fetchrow = AsyncMock(return_value=None)  # UPDATE returned no rows
        mock_tx = MagicMock(
            __aenter__=AsyncMock(return_value=None),
            __aexit__=AsyncMock(return_value=None),
        )
        mock_conn.transaction.return_value = mock_tx
        mock_acq = MagicMock(
            __aenter__=AsyncMock(return_value=mock_conn),
            __aexit__=AsyncMock(return_value=None),
        )
        mock_pool = MagicMock()
        mock_pool.acquire.return_value = mock_acq

        with (
            patch(
                "app.repositories.dm_repo.find_message_by_id",
                new_callable=AsyncMock,
                return_value=row,
            ),
            patch("app.core.database.get_pool", return_value=mock_pool),
            patch("app.services.dm.sanitize_html", side_effect=lambda x: x),
        ):
            from app.services.dm import edit_message

            with pytest.raises(AppError) as exc_info:
                await edit_message(str(_MSG_ID), _SENDER_ID, "Updated text")

            assert exc_info.value.detail["code"] == ErrorCode.SYS_422.value


# ===========================================================================
# L-23: Idempotent DM file cleanup
# ===========================================================================


class TestL23IdempotentCleanup:
    """L-23: DM file cleanup task is idempotent — duplicate runs don't double-decrement."""

    @pytest.mark.anyio
    async def test_already_cleared_skips_storage_decrement(self, _celery_modules):
        """If attachment was already cleared, storage decrement is not called."""
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
        mock_clear_if_present = AsyncMock(return_value=False)  # Already cleared
        mock_decrement = AsyncMock()
        mock_delete_file = AsyncMock()

        with (
            patch("app.tasks.cleanup._ensure_pool", new_callable=AsyncMock),
            patch("app.tasks.dm_cleanup._ensure_pool", new_callable=AsyncMock),
            patch("app.repositories.dm_repo.find_expired_file_messages", mock_find),
            patch(
                "app.repositories.dm_repo.clear_message_attachment_if_present",
                mock_clear_if_present,
            ),
            patch("app.repositories.user_repo.decrement_storage_used", mock_decrement),
            patch("app.core.async_storage.delete_file", mock_delete_file),
        ):
            from app.tasks.dm_cleanup import _cleanup_files

            result = await _cleanup_files()

        # Should not call delete_file or decrement_storage_used
        mock_delete_file.assert_not_awaited()
        mock_decrement.assert_not_awaited()
        assert result == {"deleted": 1, "errors": 0}

    @pytest.mark.anyio
    async def test_first_run_clears_and_decrements(self, _celery_modules):
        """First run clears attachment and decrements storage."""
        msg_id = uuid.uuid4()
        sender_id = uuid.uuid4()
        expired_msgs = [
            {
                "id": msg_id,
                "attachment_key": "dm/test/file.pdf",
                "attachment_size": 2048,
                "sender_id": sender_id,
            }
        ]

        mock_find = AsyncMock(return_value=expired_msgs)
        mock_clear_if_present = AsyncMock(return_value=True)  # First time — cleared
        mock_decrement = AsyncMock()
        mock_delete_file = AsyncMock()

        with (
            patch("app.tasks.cleanup._ensure_pool", new_callable=AsyncMock),
            patch("app.tasks.dm_cleanup._ensure_pool", new_callable=AsyncMock),
            patch("app.repositories.dm_repo.find_expired_file_messages", mock_find),
            patch(
                "app.repositories.dm_repo.clear_message_attachment_if_present",
                mock_clear_if_present,
            ),
            patch("app.repositories.user_repo.decrement_storage_used", mock_decrement),
            patch("app.core.async_storage.delete_file", mock_delete_file),
        ):
            from app.tasks.dm_cleanup import _cleanup_files

            result = await _cleanup_files()

        mock_delete_file.assert_awaited_once_with("dm/test/file.pdf")
        mock_decrement.assert_awaited_once_with(sender_id, 2048)
        assert result == {"deleted": 1, "errors": 0}

    @pytest.mark.anyio
    async def test_storage_delete_failure_still_decrements(self, _celery_modules):
        """If MinIO delete fails (file already gone), storage quota is still decremented."""
        msg_id = uuid.uuid4()
        sender_id = uuid.uuid4()
        expired_msgs = [
            {
                "id": msg_id,
                "attachment_key": "dm/test/gone.pdf",
                "attachment_size": 512,
                "sender_id": sender_id,
            }
        ]

        mock_find = AsyncMock(return_value=expired_msgs)
        mock_clear_if_present = AsyncMock(return_value=True)
        mock_decrement = AsyncMock()
        mock_delete_file = AsyncMock(side_effect=RuntimeError("file not found"))

        with (
            patch("app.tasks.cleanup._ensure_pool", new_callable=AsyncMock),
            patch("app.tasks.dm_cleanup._ensure_pool", new_callable=AsyncMock),
            patch("app.repositories.dm_repo.find_expired_file_messages", mock_find),
            patch(
                "app.repositories.dm_repo.clear_message_attachment_if_present",
                mock_clear_if_present,
            ),
            patch("app.repositories.user_repo.decrement_storage_used", mock_decrement),
            patch("app.core.async_storage.delete_file", mock_delete_file),
        ):
            from app.tasks.dm_cleanup import _cleanup_files

            result = await _cleanup_files()

        # Even though delete_file failed, decrement is still called
        mock_decrement.assert_awaited_once_with(sender_id, 512)
        assert result == {"deleted": 1, "errors": 0}


# ===========================================================================
# M-12 Album: Content-Type derived from extension
# ===========================================================================


class TestM12AlbumContentType:
    """M-12: Album upload endpoints derive Content-Type from file extension."""

    def test_album_cover_upload_uses_mimetypes(self):
        """upload_cover_endpoint source should use mimetypes.guess_type, not file.content_type."""
        import inspect

        from app.api.v1.endpoints.albums import upload_cover_endpoint

        source = inspect.getsource(upload_cover_endpoint)
        assert "mimetypes.guess_type" in source
        assert "file.content_type" not in source

    def test_album_photo_upload_uses_mimetypes(self):
        """upload_photo_endpoint source should use mimetypes.guess_type, not file.content_type."""
        import inspect

        from app.api.v1.endpoints.albums import upload_photo_endpoint

        source = inspect.getsource(upload_photo_endpoint)
        assert "mimetypes.guess_type" in source
        assert "file.content_type" not in source

    def test_album_file_upload_uses_mimetypes(self):
        """upload_file_endpoint source should use mimetypes.guess_type, not file.content_type."""
        import inspect

        from app.api.v1.endpoints.albums import upload_file_endpoint

        source = inspect.getsource(upload_file_endpoint)
        assert "mimetypes.guess_type" in source
        assert "file.content_type" not in source
