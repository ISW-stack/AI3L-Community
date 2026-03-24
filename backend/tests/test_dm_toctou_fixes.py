"""Tests for DM TOCTOU fixes (H-03/04/05), M-14 recall attachment cleanup,
M-15 empty content after sanitization, and M-37 post empty content after sanitization.

H-03: send_message storage quota uses FOR UPDATE inside transaction
H-04: edit_message reads message inside transaction with FOR UPDATE
H-05: recall_message reads message inside transaction with FOR UPDATE
M-14: recall_message clears attachment fields in DB
M-15: send_message rejects empty content after sanitization
M-37: create_new_post rejects HTML-only content that sanitizes to empty
"""

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.errors import AppError

_SVC = "app.services.dm"
_EP = "app.api.v1.endpoints.posts"

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


def _make_conversation(conv_id=None, user_a=None, user_b=None):
    return {
        "id": conv_id or uuid.uuid4(),
        "participant_a": uuid.UUID(user_a) if user_a else uuid.uuid4(),
        "participant_b": uuid.UUID(user_b) if user_b else uuid.uuid4(),
        "total_chars": 0,
        "created_at": _NOW,
        "updated_at": _NOW,
    }


def _make_msg_response(msg_id=None, conv_id=None, content="Hello!"):
    return {
        "id": str(msg_id or uuid.uuid4()),
        "conversation_id": str(conv_id or _CONV_ID),
        "sender": {
            "id": _SENDER_ID,
            "display_name": "Test User",
            "avatar_url": None,
        },
        "content": content,
        "attachment_url": None,
        "attachment_name": None,
        "attachment_size": None,
        "attachment_expires_at": None,
        "is_recalled": False,
        "is_edited": False,
        "read_at": None,
        "created_at": _NOW.isoformat(),
        "updated_at": _NOW.isoformat(),
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


# ── H-04: edit_message uses FOR UPDATE inside transaction ──────────────────


class TestEditMessageTOCTOU:
    """H-04: edit_message reads message with FOR UPDATE inside a transaction."""

    @pytest.mark.anyio
    @patch("app.core.database.get_pool")
    @patch(f"{_SVC}.async_row_to_message", new_callable=AsyncMock)
    @patch(f"{_SVC}.emit", new_callable=AsyncMock)
    @patch(f"{_SVC}.dm_repo")
    async def test_edit_uses_for_update_inside_transaction(
        self, mock_dm_repo, mock_emit, mock_convert, mock_get_pool
    ):
        """edit_message issues SELECT ... FOR UPDATE on the message row inside transaction."""
        msg_row = _make_message_row(sender_id=_SENDER_ID, created_at=_NOW)
        updated_row = _make_message_row(sender_id=_SENDER_ID, content="Updated!", is_edited=True)
        conv = _make_conversation(
            conv_id=msg_row["conversation_id"],
            user_a=_SENDER_ID,
            user_b=_RECIPIENT_ID,
        )

        pool, conn = _mock_pool_conn()
        conn.fetchrow = AsyncMock(side_effect=[msg_row, updated_row])
        mock_get_pool.return_value = pool

        mock_dm_repo.find_conversation_by_id = AsyncMock(return_value=conv)
        mock_convert.return_value = _make_msg_response(content="Updated!")

        from app.services.dm import edit_message

        result = await edit_message(str(_MSG_ID), _SENDER_ID, "Updated!")

        assert result["content"] == "Updated!"
        # Verify the first fetchrow call uses FOR UPDATE
        first_call_args = conn.fetchrow.call_args_list[0]
        sql = first_call_args[0][0]
        assert "FOR UPDATE" in sql, f"First fetchrow must use FOR UPDATE, got: {sql}"

    @pytest.mark.anyio
    @patch("app.core.database.get_pool")
    @patch(f"{_SVC}.async_row_to_message", new_callable=AsyncMock)
    @patch(f"{_SVC}.emit", new_callable=AsyncMock)
    @patch(f"{_SVC}.dm_repo")
    async def test_edit_computes_char_delta_from_fresh_data(
        self, mock_dm_repo, mock_emit, mock_convert, mock_get_pool
    ):
        """edit_message computes char_delta from the locked row, not stale data."""
        msg_row = _make_message_row(sender_id=_SENDER_ID, content="Short", created_at=_NOW)
        updated_row = _make_message_row(
            sender_id=_SENDER_ID,
            content="A much longer message now",
            is_edited=True,
        )
        conv = _make_conversation(
            conv_id=msg_row["conversation_id"],
            user_a=_SENDER_ID,
            user_b=_RECIPIENT_ID,
        )

        pool, conn = _mock_pool_conn()
        conn.fetchrow = AsyncMock(side_effect=[msg_row, updated_row])

        # fetchval calls: advisory lock (None), total_chars for cap check (100)
        async def mock_fetchval(*args, **kwargs):
            sql = args[0] if args else ""
            if "pg_advisory_xact_lock" in sql:
                return None
            if "total_chars" in sql:
                return 100  # well under cap
            return None

        conn.fetchval = AsyncMock(side_effect=mock_fetchval)
        mock_get_pool.return_value = pool

        mock_dm_repo.find_conversation_by_id = AsyncMock(return_value=conv)
        mock_convert.return_value = _make_msg_response(content="A much longer message now")

        from app.services.dm import edit_message

        await edit_message(str(_MSG_ID), _SENDER_ID, "A much longer message now")

        # Verify execute was called for char count update with correct delta
        assert conn.execute.called
        # Find the execute call that updates total_chars (not updated_at)
        char_update_calls = [
            c for c in conn.execute.call_args_list
            if "total_chars" in str(c[0][0])
        ]
        assert len(char_update_calls) == 1
        execute_args = char_update_calls[0][0]
        # delta = len("A much longer message now") - len("Short") = 25 - 5 = 20
        assert execute_args[1] == 20, f"Expected char_delta=20, got {execute_args[1]}"


# ── H-05: recall_message uses FOR UPDATE inside transaction ────────────────


class TestRecallMessageTOCTOU:
    """H-05: recall_message reads message with FOR UPDATE inside a transaction."""

    @pytest.mark.anyio
    @patch("app.core.database.get_pool")
    @patch(f"{_SVC}.async_row_to_message", new_callable=AsyncMock)
    @patch(f"{_SVC}.emit", new_callable=AsyncMock)
    @patch(f"{_SVC}.dm_repo")
    async def test_recall_uses_for_update_inside_transaction(
        self, mock_dm_repo, mock_emit, mock_convert, mock_get_pool
    ):
        """recall_message issues SELECT ... FOR UPDATE on the message row inside transaction."""
        msg_row = _make_message_row(sender_id=_SENDER_ID, content="Oops")
        recalled_row = _make_message_row(sender_id=_SENDER_ID, is_recalled=True, content=None)
        conv = _make_conversation(
            conv_id=msg_row["conversation_id"],
            user_a=_SENDER_ID,
            user_b=_RECIPIENT_ID,
        )

        pool, conn = _mock_pool_conn()
        conn.fetchrow = AsyncMock(side_effect=[msg_row, recalled_row])
        mock_get_pool.return_value = pool

        mock_dm_repo.find_conversation_by_id = AsyncMock(return_value=conv)
        mock_convert.return_value = _make_msg_response(content=None)

        from app.services.dm import recall_message

        result = await recall_message(str(_MSG_ID), _SENDER_ID)

        assert result is not None
        # Verify the first fetchrow call uses FOR UPDATE
        first_call_args = conn.fetchrow.call_args_list[0]
        sql = first_call_args[0][0]
        assert "FOR UPDATE" in sql, f"First fetchrow must use FOR UPDATE, got: {sql}"


# ── M-14: recall clears attachment fields in DB ───────────────────────────


class TestRecallClearsAttachmentFields:
    """M-14: recall_message should NULL out attachment_key, attachment_name,
    attachment_size, attachment_expires_at in the UPDATE SQL."""

    @pytest.mark.anyio
    @patch("app.core.database.get_pool")
    @patch(f"{_SVC}.async_row_to_message", new_callable=AsyncMock)
    @patch(f"{_SVC}.emit", new_callable=AsyncMock)
    @patch(f"{_SVC}.dm_repo")
    async def test_recall_sql_clears_attachment_fields(
        self, mock_dm_repo, mock_emit, mock_convert, mock_get_pool
    ):
        """The UPDATE SQL in recall_message sets attachment fields to NULL."""
        msg_row = _make_message_row(
            sender_id=_SENDER_ID,
            content="With file",
            attachment_key="dm/test/file.pdf",
            attachment_name="file.pdf",
            attachment_size=2048,
            attachment_expires_at=_NOW + timedelta(days=3),
        )
        recalled_row = _make_message_row(sender_id=_SENDER_ID, is_recalled=True, content=None)
        conv = _make_conversation(
            conv_id=msg_row["conversation_id"],
            user_a=_SENDER_ID,
            user_b=_RECIPIENT_ID,
        )

        pool, conn = _mock_pool_conn()
        conn.fetchrow = AsyncMock(side_effect=[msg_row, recalled_row])
        mock_get_pool.return_value = pool

        mock_dm_repo.find_conversation_by_id = AsyncMock(return_value=conv)
        mock_convert.return_value = _make_msg_response(content=None)

        with (
            patch("app.core.async_storage.delete_file", new_callable=AsyncMock),
            patch(
                "app.repositories.user_repo.decrement_storage_used",
                new_callable=AsyncMock,
            ),
        ):
            from app.services.dm import recall_message

            await recall_message(str(_MSG_ID), _SENDER_ID)

        # The second fetchrow call is the UPDATE ... RETURNING *
        update_call = conn.fetchrow.call_args_list[1]
        update_sql = update_call[0][0]
        assert (
            "attachment_key = NULL" in update_sql
        ), f"UPDATE SQL must NULL attachment_key, got: {update_sql}"
        assert (
            "attachment_name = NULL" in update_sql
        ), f"UPDATE SQL must NULL attachment_name, got: {update_sql}"
        assert (
            "attachment_size = NULL" in update_sql
        ), f"UPDATE SQL must NULL attachment_size, got: {update_sql}"
        assert (
            "attachment_expires_at = NULL" in update_sql
        ), f"UPDATE SQL must NULL attachment_expires_at, got: {update_sql}"

    @pytest.mark.anyio
    @patch("app.core.database.get_pool")
    @patch(f"{_SVC}.async_row_to_message", new_callable=AsyncMock)
    @patch(f"{_SVC}.emit", new_callable=AsyncMock)
    @patch(f"{_SVC}.dm_repo")
    async def test_recall_extracts_attachment_info_before_clearing(
        self, mock_dm_repo, mock_emit, mock_convert, mock_get_pool
    ):
        """recall_message saves attachment_key/size from the row before clearing,
        then uses them for MinIO cleanup after the transaction."""
        msg_row = _make_message_row(
            sender_id=_SENDER_ID,
            content="With file",
            attachment_key="dm/test/file.pdf",
            attachment_name="file.pdf",
            attachment_size=2048,
        )
        recalled_row = _make_message_row(sender_id=_SENDER_ID, is_recalled=True, content=None)
        conv = _make_conversation(
            conv_id=msg_row["conversation_id"],
            user_a=_SENDER_ID,
            user_b=_RECIPIENT_ID,
        )

        pool, conn = _mock_pool_conn()
        conn.fetchrow = AsyncMock(side_effect=[msg_row, recalled_row])
        mock_get_pool.return_value = pool

        mock_dm_repo.find_conversation_by_id = AsyncMock(return_value=conv)
        mock_convert.return_value = _make_msg_response(content=None)

        with (
            patch("app.core.async_storage.delete_file", new_callable=AsyncMock) as mock_delete,
            patch(
                "app.repositories.user_repo.decrement_storage_used",
                new_callable=AsyncMock,
            ) as mock_decrement,
        ):
            from app.services.dm import recall_message

            await recall_message(str(_MSG_ID), _SENDER_ID)

        # Verify cleanup still happens with correct values from pre-clear row
        mock_delete.assert_awaited_once_with("dm/test/file.pdf")
        mock_decrement.assert_called_once_with(uuid.UUID(_SENDER_ID), 2048)


# ── H-03: send_message quota check uses FOR UPDATE ────────────────────────


class TestSendMessageQuotaTOCTOU:
    """H-03: send_message storage quota check uses SELECT ... FOR UPDATE."""

    @pytest.mark.anyio
    @patch(f"{_SVC}.async_row_to_message", new_callable=AsyncMock)
    @patch(f"{_SVC}.emit", new_callable=AsyncMock)
    @patch(f"{_SVC}.dm_repo")
    async def test_send_quota_check_uses_atomic_update(self, mock_dm_repo, mock_emit, mock_convert):
        """send_message quota check uses atomic UPDATE ... RETURNING to prevent TOCTOU."""
        # We need two pools: one for block/friendship check, one for quota check
        pool, conn = _mock_pool_conn()
        conv = _make_conversation(conv_id=_CONV_ID)
        msg_row = _make_message_row(sender_id=_SENDER_ID, attachment_key="dm/f.pdf")
        msg_dict = _make_msg_response()

        mock_dm_repo.find_or_create_conversation = AsyncMock(return_value=conv)
        mock_dm_repo.send_message_atomic = AsyncMock(return_value=(msg_row, []))
        mock_dm_repo.get_dm_friends_only = AsyncMock(return_value=False)
        mock_convert.return_value = msg_dict

        # Track all fetchval calls to verify atomic UPDATE pattern
        fetchval_calls = []

        async def track_fetchval(*args, **kwargs):
            fetchval_calls.append(args)
            return 0  # storage_used_bytes / dm_friends_only = 0/False

        conn.fetchval = AsyncMock(side_effect=track_fetchval)

        with (
            patch("app.core.database.get_pool", return_value=pool),
            patch(
                "app.repositories.social_repo.is_blocked",
                new_callable=AsyncMock,
                return_value=False,
            ),
            patch(
                "app.repositories.user_repo.increment_storage_used",
                new_callable=AsyncMock,
            ),
            patch("app.core.async_storage.upload_file", new_callable=AsyncMock),
            patch(
                "app.core.storage.generate_presigned_url",
                return_value="http://presigned",
            ),
            patch(f"{_SVC}._validate_dm_file"),
            patch(
                "app.repositories.user_repo.find_by_id",
                new_callable=AsyncMock,
                return_value={"id": _RECIPIENT_ID, "is_deleted": False},
            ),
        ):
            from app.services.dm import send_message

            await send_message(
                sender_id=_SENDER_ID,
                recipient_id=_RECIPIENT_ID,
                file_data=b"data",
                file_name="file.pdf",
                file_size=1024,
                file_content_type="application/pdf",
            )

        # Verify atomic UPDATE ... RETURNING was used for quota check
        atomic_update_found = any(
            len(args) > 0 and "UPDATE users" in str(args[0])
            and "RETURNING" in str(args[0])
            for args in fetchval_calls
        )
        assert atomic_update_found, (
            f"Expected an atomic UPDATE ... RETURNING for quota, got calls: {fetchval_calls}"
        )

    @pytest.mark.anyio
    @patch(f"{_SVC}.dm_repo")
    async def test_send_quota_exceeded_returns_413(self, mock_dm_repo):
        """send_message with quota exceeded raises DM_004 with 413."""
        pool, conn = _mock_pool_conn()

        # fetchval calls: dm_friends_only (False), then atomic UPDATE returns None (quota exceeded)
        conn.fetchval = AsyncMock(side_effect=[False, None])

        with (
            patch("app.core.database.get_pool", return_value=pool),
            patch(
                "app.repositories.social_repo.is_blocked",
                new_callable=AsyncMock,
                return_value=False,
            ),
            patch(f"{_SVC}._validate_dm_file"),
            patch(
                "app.repositories.user_repo.find_by_id",
                new_callable=AsyncMock,
                return_value={"id": _RECIPIENT_ID, "is_deleted": False},
            ),
        ):
            from app.services.dm import send_message

            with pytest.raises(AppError) as exc:
                await send_message(
                    sender_id=_SENDER_ID,
                    recipient_id=_RECIPIENT_ID,
                    file_data=b"data",
                    file_name="file.pdf",
                    file_size=1024,
                    file_content_type="application/pdf",
                )

        assert exc.value.status_code == 413


# ── M-15: send_message rejects empty content after sanitization ────────────


class TestSendMessageEmptyAfterSanitization:
    """M-15: send_message rejects content that becomes empty after sanitization."""

    @pytest.mark.anyio
    async def test_send_script_only_content_rejected(self):
        """send_message with script-only content (sanitizes to empty) raises 422."""
        with (
            patch(f"{_SVC}.sanitize_html", return_value=""),
            patch(
                "app.repositories.user_repo.find_by_id",
                new_callable=AsyncMock,
                return_value={"id": _RECIPIENT_ID, "is_deleted": False},
            ),
        ):
            from app.services.dm import send_message

            with pytest.raises(AppError) as exc:
                await send_message(
                    sender_id=_SENDER_ID,
                    recipient_id=_RECIPIENT_ID,
                    content="<script>alert('xss')</script>",
                )

            assert exc.value.status_code == 422
            assert "content or an attachment" in exc.value.detail["message"]

    @pytest.mark.anyio
    async def test_send_whitespace_only_after_sanitize_rejected(self):
        """send_message with content that sanitizes to whitespace raises 422."""
        with (
            patch(f"{_SVC}.sanitize_html", return_value="   "),
            patch(
                "app.repositories.user_repo.find_by_id",
                new_callable=AsyncMock,
                return_value={"id": _RECIPIENT_ID, "is_deleted": False},
            ),
        ):
            from app.services.dm import send_message

            with pytest.raises(AppError) as exc:
                await send_message(
                    sender_id=_SENDER_ID,
                    recipient_id=_RECIPIENT_ID,
                    content="<b>  </b>",
                )

            assert exc.value.status_code == 422

    @pytest.mark.anyio
    @patch(f"{_SVC}.async_row_to_message", new_callable=AsyncMock)
    @patch(f"{_SVC}.emit", new_callable=AsyncMock)
    @patch(f"{_SVC}.dm_repo")
    async def test_send_empty_content_with_file_allowed(
        self, mock_dm_repo, mock_emit, mock_convert
    ):
        """send_message allows empty content after sanitization if file is attached."""
        pool, conn = _mock_pool_conn()
        conv = _make_conversation(conv_id=_CONV_ID)
        msg_row = _make_message_row(sender_id=_SENDER_ID, content=None, attachment_key="dm/f.pdf")
        msg_dict = _make_msg_response(content=None)

        mock_dm_repo.find_or_create_conversation = AsyncMock(return_value=conv)
        mock_dm_repo.send_message_atomic = AsyncMock(return_value=(msg_row, []))
        mock_dm_repo.get_dm_friends_only = AsyncMock(return_value=False)
        mock_convert.return_value = msg_dict

        conn.fetchval = AsyncMock(return_value=0)

        with (
            patch("app.core.database.get_pool", return_value=pool),
            patch(
                "app.repositories.social_repo.is_blocked",
                new_callable=AsyncMock,
                return_value=False,
            ),
            patch(
                "app.repositories.user_repo.increment_storage_used",
                new_callable=AsyncMock,
            ),
            patch("app.core.async_storage.upload_file", new_callable=AsyncMock),
            patch(
                "app.core.storage.generate_presigned_url",
                return_value="http://presigned",
            ),
            patch(f"{_SVC}._validate_dm_file"),
            patch(f"{_SVC}.sanitize_html", return_value=""),
            patch(
                "app.repositories.user_repo.find_by_id",
                new_callable=AsyncMock,
                return_value={"id": _RECIPIENT_ID, "is_deleted": False},
            ),
        ):
            from app.services.dm import send_message

            # Should not raise because file_data is provided
            result = await send_message(
                sender_id=_SENDER_ID,
                recipient_id=_RECIPIENT_ID,
                content="<script>xss</script>",
                file_data=b"data",
                file_name="file.pdf",
                file_size=1024,
                file_content_type="application/pdf",
            )

        assert result is not None


# ── M-37: create_new_post rejects empty content after sanitization ─────────


def _override_auth(role="MEMBER", user_id=None):
    from app.core.deps import get_current_user
    from app.main import app

    uid = user_id or str(uuid.uuid4())
    payload = {"sub": uid, "role": role, "jti": str(uuid.uuid4())}
    app.dependency_overrides[get_current_user] = lambda: payload
    return payload, uid


def _clear_overrides():
    from app.main import app

    app.dependency_overrides.clear()


class TestCreatePostEmptyAfterSanitization:
    """M-37: POST /posts rejects content that sanitizes to empty."""

    @pytest.mark.anyio
    async def test_create_post_script_only_content_rejected(self, client):
        """POST /posts with script-only content returns 400."""
        user_id = str(uuid.uuid4())
        try:
            _override_auth("MEMBER", user_id=user_id)
            with patch(f"{_EP}.sanitize_html", return_value=""):
                resp = await client.post(
                    "/api/v1/posts",
                    json={
                        "title": "Test",
                        "content": "<script>alert('xss')</script>",
                    },
                )
            assert resp.status_code == 400
            detail = resp.json()["detail"]
            msg = detail["message"] if isinstance(detail, dict) else detail
            assert "empty" in msg.lower()
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_create_post_whitespace_only_after_sanitize_rejected(self, client):
        """POST /posts with content that sanitizes to whitespace returns 400."""
        user_id = str(uuid.uuid4())
        try:
            _override_auth("MEMBER", user_id=user_id)
            with patch(f"{_EP}.sanitize_html", return_value="   "):
                resp = await client.post(
                    "/api/v1/posts",
                    json={"title": "Test", "content": "<b>  </b>"},
                )
            assert resp.status_code == 400
            detail = resp.json()["detail"]
            msg = detail["message"] if isinstance(detail, dict) else detail
            assert "empty" in msg.lower()
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_create_post_valid_content_passes(self, client):
        """POST /posts with valid content after sanitization returns 201."""
        user_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        post = {
            "id": str(uuid.uuid4()),
            "title": "Test",
            "content": "<p>Valid content</p>",
            "author": {
                "id": user_id,
                "username": "testuser",
                "display_name": "Test User",
                "avatar_url": None,
            },
            "category_id": None,
            "category_name": None,
            "keywords": [],
            "allow_comments": True,
            "version": 1,
            "comment_count": 0,
            "created_at": now,
            "updated_at": now,
        }
        try:
            _override_auth("MEMBER", user_id=user_id)
            with patch(
                f"{_EP}.create_post",
                new_callable=AsyncMock,
                return_value=post,
            ):
                resp = await client.post(
                    "/api/v1/posts",
                    json={
                        "title": "Test",
                        "content": "<p>Valid content</p>",
                    },
                )
            assert resp.status_code == 201
        finally:
            _clear_overrides()
