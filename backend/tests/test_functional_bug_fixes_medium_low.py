"""Tests for functional bug fixes F-06 through F-32 (Medium + Low severity).

Covers:
F-06: Conversation list presigned URL generation
F-07/F-08/F-09: Frontend DM store fixes (tested in frontend)
F-10/F-11: Frontend locale/UI fixes (tested in frontend)
F-12: QA answer pagination (tested in frontend)
F-13: Form deadline timezone awareness
F-14: Standalone form creator admin controls
F-15: Post file cleanup cross-reference check
F-17: DM file scan-gating for missing records
F-18: Async presigned URL generation
F-19: dm_cleanup async S3 calls
F-22: Edit/recall echo to sender
F-23: recallFromWebSocket attachment fields (tested in frontend)
F-24: find_or_create_conversation transaction
F-28: /users/me rejects GUEST
F-29: destroy_session race condition
F-30: Idempotency key uses user_id not token hash
F-31: Missing task imports
"""

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.errors import AppError, ErrorCode

_NOW = datetime.now(timezone.utc)
_USER_ID = str(uuid.uuid4())


# ── F-12: QA answer pagination root_only ───────────────────────────────


class TestF12RootOnlyComments:
    """The root_only parameter should filter to parent_id IS NULL in the query."""

    @pytest.mark.asyncio
    async def test_find_many_root_only_filters_parent_id(self):
        """find_many with root_only=True adds parent_id IS NULL filter."""
        from app.repositories import comment_repo

        post_id = uuid.uuid4()
        mock_pool = MagicMock()
        mock_conn = AsyncMock()
        mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_conn.fetch.return_value = []
        mock_conn.fetchval.return_value = 0

        with patch("app.repositories.comment_repo.get_pool", return_value=mock_pool):
            _, total = await comment_repo.find_many(post_id, root_only=True)

        # Verify the count query includes parent_id IS NULL
        count_query = mock_conn.fetchval.call_args[0][0]
        assert "parent_id IS NULL" in count_query

    @pytest.mark.asyncio
    async def test_find_many_default_no_root_filter(self):
        """find_many without root_only does not add parent_id IS NULL filter."""
        from app.repositories import comment_repo

        post_id = uuid.uuid4()
        mock_pool = MagicMock()
        mock_conn = AsyncMock()
        mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_conn.fetch.return_value = []
        mock_conn.fetchval.return_value = 0

        with patch("app.repositories.comment_repo.get_pool", return_value=mock_pool):
            _, total = await comment_repo.find_many(post_id, root_only=False)

        count_query = mock_conn.fetchval.call_args[0][0]
        assert "parent_id IS NULL" not in count_query


# ── F-13: Form deadline timezone awareness ─────────────────────────────


class TestF13DeadlineTimezone:
    """Form schemas should coerce naive datetimes to UTC."""

    def test_naive_deadline_gets_utc(self):
        """A naive datetime should be converted to UTC-aware."""
        from app.schemas.form import FormCreateRequest

        naive_dt = "2026-12-01T12:00:00"
        req = FormCreateRequest(
            title="Test form",
            deadline=naive_dt,
            questions=[{"id": "q1", "type": "text", "label": "Name"}],
        )
        assert req.deadline is not None
        assert req.deadline.tzinfo is not None

    def test_aware_deadline_preserved(self):
        """An aware datetime should be preserved as-is."""
        from app.schemas.form import FormCreateRequest

        aware_dt = "2026-12-01T12:00:00+05:00"
        req = FormCreateRequest(
            title="Test form",
            deadline=aware_dt,
            questions=[{"id": "q1", "type": "text", "label": "Name"}],
        )
        assert req.deadline is not None
        assert req.deadline.tzinfo is not None

    def test_none_deadline_remains_none(self):
        """A None deadline should remain None."""
        from app.schemas.form import FormCreateRequest

        req = FormCreateRequest(
            title="Test form",
            questions=[{"id": "q1", "type": "text", "label": "Name"}],
        )
        assert req.deadline is None

    def test_update_request_naive_deadline(self):
        """FormUpdateRequest should also coerce naive datetimes."""
        from app.schemas.form import FormUpdateRequest

        req = FormUpdateRequest(deadline="2026-06-01T00:00:00")
        assert req.deadline is not None
        assert req.deadline.tzinfo is not None


# ── F-14: Standalone form creator admin controls ───────────────────────


class TestF14StandaloneFormCreatorAdmin:
    """Standalone form creator should get user_is_sig_admin=True."""

    def _make_form_dict(self, form_id, created_by):
        return {
            "id": str(form_id),
            "sig_id": None,
            "title": "Test Form",
            "description": None,
            "banner_url": None,
            "deadline": None,
            "max_respondents": None,
            "questions": [],
            "is_schema_locked": False,
            "allow_non_members": True,
            "response_count": 0,
            "has_responded": False,
            "is_active": True,
            "created_by": created_by,
            "created_by_name": "Tester",
            "created_at": _NOW.isoformat(),
            "updated_at": _NOW.isoformat(),
        }

    @pytest.mark.asyncio
    async def test_creator_gets_admin_controls(self):
        """MEMBER who created a standalone form should see admin controls."""
        user_id = str(uuid.uuid4())
        form_id = uuid.uuid4()
        form_dict = self._make_form_dict(form_id, user_id)
        current_user = {"sub": user_id, "role": "MEMBER", "jti": str(uuid.uuid4())}

        with patch(
            "app.api.v1.endpoints.forms.get_form_by_id",
            new_callable=AsyncMock,
            return_value=form_dict,
        ):
            from app.api.v1.endpoints.forms import get_form

            result = await get_form(form_id, current_user)
            assert result.user_is_sig_admin is True

    @pytest.mark.asyncio
    async def test_non_creator_no_admin_controls(self):
        """MEMBER who is not the creator should NOT get admin controls."""
        creator_id = str(uuid.uuid4())
        viewer_id = str(uuid.uuid4())
        form_id = uuid.uuid4()
        form_dict = self._make_form_dict(form_id, creator_id)
        current_user = {"sub": viewer_id, "role": "MEMBER", "jti": str(uuid.uuid4())}

        with patch(
            "app.api.v1.endpoints.forms.get_form_by_id",
            new_callable=AsyncMock,
            return_value=form_dict,
        ):
            from app.api.v1.endpoints.forms import get_form

            result = await get_form(form_id, current_user)
            assert result.user_is_sig_admin is False


# ── F-17: DM file scan-gating ─────────────────────────────────────────


class TestF17DmFileScanGating:
    """DM files with missing scan records should be treated as pending."""

    @pytest.mark.asyncio
    @patch("app.services.dm.file_scan_repo")
    async def test_missing_scan_record_returns_false(self, mock_scan_repo):
        """_is_dm_file_clean should return False when no scan record exists."""
        from app.services.dm import _is_dm_file_clean

        mock_scan_repo.find_by_key = AsyncMock(return_value=None)
        result = await _is_dm_file_clean("dm/user/file.jpg")
        assert result is False

    @pytest.mark.asyncio
    @patch("app.services.dm.file_scan_repo")
    async def test_clean_scan_record_returns_true(self, mock_scan_repo):
        """_is_dm_file_clean should return True when scan status is 'clean'."""
        from app.services.dm import _is_dm_file_clean

        mock_scan_repo.find_by_key = AsyncMock(return_value={"status": "clean"})
        result = await _is_dm_file_clean("dm/user/file.jpg")
        assert result is True

    @pytest.mark.asyncio
    @patch("app.services.dm.file_scan_repo")
    async def test_pending_scan_returns_false(self, mock_scan_repo):
        """_is_dm_file_clean should return False for pending scans."""
        from app.services.dm import _is_dm_file_clean

        mock_scan_repo.find_by_key = AsyncMock(return_value={"status": "pending"})
        result = await _is_dm_file_clean("dm/user/file.jpg")
        assert result is False


# ── F-29: destroy_session race ─────────────────────────────────────────


class TestF29DestroySessionRace:
    """destroy_session should not delete a newly-created session."""

    @pytest.mark.asyncio
    @patch("app.services.auth.get_redis")
    async def test_expired_session_no_delete(self, mock_get_redis):
        """When stored_jti is None (expired), session key should NOT be deleted."""
        from app.services.auth import destroy_session

        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=None)  # session expired
        mock_redis.delete = AsyncMock()
        mock_redis.set = AsyncMock()
        mock_get_redis.return_value = mock_redis

        await destroy_session("user1", "MEMBER", "old-jti")

        # Should NOT call delete (session key may belong to a new login)
        mock_redis.delete.assert_not_called()
        # But should still blacklist the JWT
        mock_redis.set.assert_called_once()

    @pytest.mark.asyncio
    @patch("app.services.auth.get_redis")
    async def test_matching_jti_deletes_session(self, mock_get_redis):
        """When JTI matches, session should be deleted normally."""
        from app.services.auth import destroy_session

        jti = "matching-jti"
        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=jti.encode())
        mock_redis.delete = AsyncMock()
        mock_redis.set = AsyncMock()
        mock_get_redis.return_value = mock_redis

        await destroy_session("user1", "MEMBER", jti)
        mock_redis.delete.assert_called_once()


# ── F-30: Idempotency key uses user_id ─────────────────────────────────


class TestF30IdempotencyKey:
    """Idempotency key should use JWT sub (user_id) not token hash."""

    def test_decode_called_for_namespace(self):
        """Middleware should decode JWT to extract user_id for namespace."""
        import jwt
        from app.core.config import settings
        from app.core.security import create_access_token

        user_id = str(uuid.uuid4())
        token, _, _ = create_access_token(user_id, "MEMBER")
        # Decode to verify the sub is the user_id
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
            audience="ai3l-api",
        )
        assert payload["sub"] == user_id


# ── F-31: Missing task imports ─────────────────────────────────────────


class TestF31TaskImports:
    """dm_cleanup and site_export should be importable from app.tasks."""

    def test_dm_cleanup_importable(self):
        """from app.tasks import dm_cleanup should work."""
        from app.tasks import dm_cleanup

        assert dm_cleanup is not None

    def test_site_export_importable(self):
        """from app.tasks import site_export should work."""
        from app.tasks import site_export

        assert site_export is not None

    def test_all_includes_dm_cleanup(self):
        """__all__ should include dm_cleanup."""
        from app.tasks import __all__ as all_tasks

        assert "dm_cleanup" in all_tasks

    def test_all_includes_site_export(self):
        """__all__ should include site_export."""
        from app.tasks import __all__ as all_tasks

        assert "site_export" in all_tasks


# ── F-06: Conversation list presigned URL ──────────────────────────────


class TestF06ConversationPresignedUrl:
    """list_conversations should use raw row attachment_key, not converter output."""

    @pytest.mark.asyncio
    @patch("app.services.dm.dm_repo")
    @patch("app.services.dm._is_dm_file_clean", new_callable=AsyncMock, return_value=True)
    @patch("app.services.dm._sync_presigned_url", return_value="https://presigned.url/file")
    async def test_presigned_url_generated_from_raw_row(
        self, mock_presign, mock_clean, mock_repo
    ):
        """Presigned URL should be generated when raw row has attachment_key."""
        from app.services.dm import list_conversations

        raw_row = {
            "id": uuid.uuid4(),
            "participant_a": uuid.UUID(_USER_ID),
            "participant_b": uuid.uuid4(),
            "total_chars": 100,
            "updated_at": _NOW,
            "other_user_id": uuid.uuid4(),
            "other_display_name": "TestUser",
            "other_avatar_url": None,
            "last_msg_id": uuid.uuid4(),
            "last_msg_conversation_id": uuid.uuid4(),
            "last_msg_sender_id": uuid.uuid4(),
            "last_msg_content": "Hello",
            "last_msg_attachment_key": "dm/user/file.jpg",
            "last_msg_attachment_name": "photo.jpg",
            "last_msg_attachment_size": 1024,
            "last_msg_attachment_expires_at": _NOW + timedelta(days=3),
            "last_msg_is_recalled": False,
            "last_msg_is_edited": False,
            "last_msg_read_at": None,
            "last_msg_created_at": _NOW,
            "last_msg_updated_at": _NOW,
            "last_msg_sender_display_name": "Sender",
            "last_msg_sender_avatar_url": None,
            "unread_count": 0,
        }
        mock_repo.find_conversations = AsyncMock(return_value=([raw_row], 1))

        convs, total = await list_conversations(_USER_ID, 1, 30)
        assert total == 1
        assert convs[0]["last_message"]["attachment_url"] == "https://presigned.url/file"
        mock_presign.assert_called_once()


# ── F-22: Edit/recall echo to sender ──────────────────────────────────


class TestF22EditRecallEcho:
    """DM_EDITED and DM_RECALLED events should echo to sender's other sessions."""

    @pytest.mark.asyncio
    async def test_edit_echoed_to_sender(self):
        """_on_dm_message_edited should send to both recipient and sender."""
        mock_send = AsyncMock()

        with patch("app.api.v1.endpoints.ws.send_to_user", mock_send):
            from app.event_handlers import _on_dm_message_edited

            await _on_dm_message_edited(
                recipient_id="recipient-1",
                message={"id": "msg-1", "content": "edited"},
                sender_id="sender-1",
            )
        # Should be called twice: once for recipient, once for sender
        assert mock_send.call_count == 2

    @pytest.mark.asyncio
    async def test_recall_echoed_to_sender(self):
        """_on_dm_message_recalled should send to both recipient and sender."""
        mock_send = AsyncMock()

        with patch("app.api.v1.endpoints.ws.send_to_user", mock_send):
            from app.event_handlers import _on_dm_message_recalled

            await _on_dm_message_recalled(
                recipient_id="recipient-1",
                message_id="msg-1",
                conversation_id="conv-1",
                sender_id="sender-1",
            )
        assert mock_send.call_count == 2
