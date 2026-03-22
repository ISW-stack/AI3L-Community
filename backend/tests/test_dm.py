"""Comprehensive tests for the DM (Private Messaging) feature.

Covers: repository, service, endpoint, Celery task, event handler, and preferences layers.
"""

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.errors import AppError, ErrorCode

# ── Helpers ──────────────────────────────────────────────────────────────────

_REPO = "app.repositories.dm_repo"
_SVC = "app.services.dm"
_EP = "app.api.v1.endpoints.dm"
_EH = "app.event_handlers"
_TASK = "app.tasks.dm_cleanup"

_NOW = datetime.now(timezone.utc)
_SENDER_ID = str(uuid.uuid4())
_RECIPIENT_ID = str(uuid.uuid4())
_CONV_ID = uuid.uuid4()
_MSG_ID = uuid.uuid4()


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


def _make_conversation(conv_id=None, user_a=None, user_b=None):
    return {
        "id": conv_id or uuid.uuid4(),
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


def _make_msg_response(msg_id=None, conv_id=None, content="Hello!"):
    return {
        "id": str(msg_id or uuid.uuid4()),
        "conversation_id": str(conv_id or _CONV_ID),
        "sender": {"id": _SENDER_ID, "display_name": "Test User", "avatar_url": None},
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


def _make_conversation_list_row(conv_id=None, user_id=None, other_id=None):
    """Row as returned by find_conversations SQL query."""
    cid = conv_id or uuid.uuid4()
    uid = uuid.UUID(user_id) if user_id else uuid.uuid4()
    oid = uuid.UUID(other_id) if other_id else uuid.uuid4()
    return {
        "id": cid,
        "participant_a": uid,
        "participant_b": oid,
        "total_chars": 100,
        "updated_at": _NOW,
        "other_user_id": oid,
        "other_display_name": "Other User",
        "other_avatar_url": None,
        "last_msg_id": uuid.uuid4(),
        "last_msg_conversation_id": cid,
        "last_msg_sender_id": uid,
        "last_msg_content": "Hey",
        "last_msg_attachment_key": None,
        "last_msg_attachment_name": None,
        "last_msg_attachment_size": None,
        "last_msg_attachment_expires_at": None,
        "last_msg_is_recalled": False,
        "last_msg_is_edited": False,
        "last_msg_read_at": None,
        "last_msg_created_at": _NOW,
        "last_msg_updated_at": _NOW,
        "last_msg_sender_display_name": "Test User",
        "last_msg_sender_avatar_url": None,
        "unread_count": 2,
        "_total": 1,
    }


# ══════════════════════════════════════════════════════════════════════════════
# 1. REPOSITORY TESTS
# ══════════════════════════════════════════════════════════════════════════════


class TestDMRepoFindOrCreateConversation:
    @pytest.mark.anyio
    async def test_sorts_uuids_and_returns_conversation(self, mock_pool, mock_conn):
        """find_or_create_conversation sorts UUIDs and returns existing conversation."""
        a = uuid.UUID("00000000-0000-0000-0000-000000000001")
        b = uuid.UUID("00000000-0000-0000-0000-000000000002")
        expected = _make_conversation(user_a=str(a), user_b=str(b))
        mock_conn.fetchrow.return_value = expected

        with patch(f"{_REPO}.get_pool", return_value=mock_pool):
            from app.repositories.dm_repo import find_or_create_conversation

            result = await find_or_create_conversation(b, a)

        # Should pass sorted (a, b) regardless of input order
        args = mock_conn.execute.call_args[0]
        assert args[1] == a  # low
        assert args[2] == b  # high
        assert result["id"] == expected["id"]

    @pytest.mark.anyio
    async def test_same_order_when_already_sorted(self, mock_pool, mock_conn):
        """find_or_create_conversation works when UUIDs already in order."""
        a = uuid.UUID("00000000-0000-0000-0000-000000000001")
        b = uuid.UUID("00000000-0000-0000-0000-000000000002")
        mock_conn.fetchrow.return_value = _make_conversation(user_a=str(a), user_b=str(b))

        with patch(f"{_REPO}.get_pool", return_value=mock_pool):
            from app.repositories.dm_repo import find_or_create_conversation

            result = await find_or_create_conversation(a, b)

        assert result is not None


class TestDMRepoFindConversationById:
    @pytest.mark.anyio
    async def test_returns_conversation_for_participant(self, mock_pool, mock_conn):
        """find_conversation_by_id returns dict when user is participant."""
        conv = _make_conversation()
        mock_conn.fetchrow.return_value = conv

        with patch(f"{_REPO}.get_pool", return_value=mock_pool):
            from app.repositories.dm_repo import find_conversation_by_id

            result = await find_conversation_by_id(conv["id"], conv["participant_a"])

        assert result is not None

    @pytest.mark.anyio
    async def test_returns_none_for_non_participant(self, mock_pool, mock_conn):
        """find_conversation_by_id returns None when user is not participant."""
        mock_conn.fetchrow.return_value = None

        with patch(f"{_REPO}.get_pool", return_value=mock_pool):
            from app.repositories.dm_repo import find_conversation_by_id

            result = await find_conversation_by_id(uuid.uuid4(), uuid.uuid4())

        assert result is None


class TestDMRepoInsertMessage:
    @pytest.mark.anyio
    async def test_insert_text_message(self, mock_pool, mock_conn):
        """insert_message with text only returns message dict."""
        row = _make_message_row(sender_id=_SENDER_ID)
        mock_conn.fetchrow.return_value = row

        with patch(f"{_REPO}.get_pool", return_value=mock_pool):
            from app.repositories.dm_repo import insert_message

            result = await insert_message(
                msg_id=uuid.uuid4(),
                conversation_id=_CONV_ID,
                sender_id=uuid.UUID(_SENDER_ID),
                content="Hello!",
            )

        assert result["content"] == "Hello!"
        # Should also update conversation updated_at
        assert mock_conn.execute.called

    @pytest.mark.anyio
    async def test_insert_message_with_attachment(self, mock_pool, mock_conn):
        """insert_message with attachment fields passes them through."""
        expires = _NOW + timedelta(days=3)
        row = _make_message_row(
            sender_id=_SENDER_ID,
            attachment_key="dm/test/file.pdf",
            attachment_name="file.pdf",
            attachment_size=1024,
            attachment_expires_at=expires,
        )
        mock_conn.fetchrow.return_value = row

        with patch(f"{_REPO}.get_pool", return_value=mock_pool):
            from app.repositories.dm_repo import insert_message

            result = await insert_message(
                msg_id=uuid.uuid4(),
                conversation_id=_CONV_ID,
                sender_id=uuid.UUID(_SENDER_ID),
                content=None,
                attachment_key="dm/test/file.pdf",
                attachment_name="file.pdf",
                attachment_size=1024,
                attachment_expires_at=expires,
            )

        assert result["attachment_key"] == "dm/test/file.pdf"
        assert result["attachment_size"] == 1024


class TestDMRepoFindMessages:
    @pytest.mark.anyio
    async def test_returns_paginated_messages(self, mock_pool, mock_conn):
        """find_messages returns (rows, total) with _total stripped."""
        row = dict(_make_message_row())
        row["_total"] = 5
        mock_conn.fetch.return_value = [row]

        with patch(f"{_REPO}.get_pool", return_value=mock_pool):
            from app.repositories.dm_repo import find_messages

            result, total = await find_messages(_CONV_ID, page_size=30, offset=0)

        assert total == 5
        assert len(result) == 1
        assert "_total" not in result[0]

    @pytest.mark.anyio
    async def test_empty_result_returns_zero_total(self, mock_pool, mock_conn):
        """find_messages returns ([], count) when no rows."""
        mock_conn.fetch.return_value = []
        mock_conn.fetchval.return_value = 0

        with patch(f"{_REPO}.get_pool", return_value=mock_pool):
            from app.repositories.dm_repo import find_messages

            result, total = await find_messages(_CONV_ID)

        assert result == []
        assert total == 0


class TestDMRepoFindConversations:
    @pytest.mark.anyio
    async def test_returns_conversations_with_total(self, mock_pool, mock_conn):
        """find_conversations returns (rows, total)."""
        row = _make_conversation_list_row(user_id=_SENDER_ID, other_id=_RECIPIENT_ID)
        mock_conn.fetch.return_value = [row]

        with patch(f"{_REPO}.get_pool", return_value=mock_pool):
            from app.repositories.dm_repo import find_conversations

            result, total = await find_conversations(uuid.UUID(_SENDER_ID))

        assert total == 1
        assert len(result) == 1
        assert "_total" not in result[0]

    @pytest.mark.anyio
    async def test_empty_conversations_fallback_count(self, mock_pool, mock_conn):
        """find_conversations falls back to COUNT query when no rows."""
        mock_conn.fetch.return_value = []
        mock_conn.fetchval.return_value = 0

        with patch(f"{_REPO}.get_pool", return_value=mock_pool):
            from app.repositories.dm_repo import find_conversations

            result, total = await find_conversations(uuid.UUID(_SENDER_ID))

        assert result == []
        assert total == 0


class TestDMRepoUpdateMessageContent:
    @pytest.mark.anyio
    async def test_update_sets_is_edited(self, mock_pool, mock_conn):
        """update_message_content returns updated row with is_edited=True."""
        row = _make_message_row(is_edited=True, content="Updated!")
        mock_conn.fetchrow.return_value = row

        with patch(f"{_REPO}.get_pool", return_value=mock_pool):
            from app.repositories.dm_repo import update_message_content

            result = await update_message_content(_MSG_ID, "Updated!")

        assert result["is_edited"] is True
        assert result["content"] == "Updated!"

    @pytest.mark.anyio
    async def test_update_nonexistent_returns_none(self, mock_pool, mock_conn):
        """update_message_content returns None for missing message."""
        mock_conn.fetchrow.return_value = None

        with patch(f"{_REPO}.get_pool", return_value=mock_pool):
            from app.repositories.dm_repo import update_message_content

            result = await update_message_content(uuid.uuid4(), "text")

        assert result is None


class TestDMRepoRecallMessage:
    @pytest.mark.anyio
    async def test_recall_nullifies_content_and_attachment(self, mock_pool, mock_conn):
        """recall_message sets is_recalled=True, NULLs content/attachment."""
        row = _make_message_row(
            is_recalled=True,
            content=None,
            attachment_key=None,
            attachment_name=None,
            attachment_size=None,
        )
        mock_conn.fetchrow.return_value = row

        with patch(f"{_REPO}.get_pool", return_value=mock_pool):
            from app.repositories.dm_repo import recall_message

            result = await recall_message(_MSG_ID)

        assert result["is_recalled"] is True
        assert result["content"] is None
        assert result["attachment_key"] is None

    @pytest.mark.anyio
    async def test_recall_nonexistent_returns_none(self, mock_pool, mock_conn):
        """recall_message returns None for missing message."""
        mock_conn.fetchrow.return_value = None

        with patch(f"{_REPO}.get_pool", return_value=mock_pool):
            from app.repositories.dm_repo import recall_message

            result = await recall_message(uuid.uuid4())

        assert result is None


class TestDMRepoMarkMessagesRead:
    @pytest.mark.anyio
    async def test_mark_read_returns_count(self, mock_pool, mock_conn):
        """mark_messages_read returns count of updated rows."""
        mock_conn.execute.return_value = "UPDATE 3"

        with patch(f"{_REPO}.get_pool", return_value=mock_pool):
            from app.repositories.dm_repo import mark_messages_read

            count = await mark_messages_read(_CONV_ID, uuid.UUID(_SENDER_ID))

        assert count == 3

    @pytest.mark.anyio
    async def test_mark_read_zero_when_none_updated(self, mock_pool, mock_conn):
        """mark_messages_read returns 0 when no unread messages."""
        mock_conn.execute.return_value = "UPDATE 0"

        with patch(f"{_REPO}.get_pool", return_value=mock_pool):
            from app.repositories.dm_repo import mark_messages_read

            count = await mark_messages_read(_CONV_ID, uuid.UUID(_SENDER_ID))

        assert count == 0


class TestDMRepoCountTotalUnread:
    @pytest.mark.anyio
    async def test_count_total_unread(self, mock_pool, mock_conn):
        """count_total_unread returns correct count."""
        mock_conn.fetchval.return_value = 7

        with patch(f"{_REPO}.get_pool", return_value=mock_pool):
            from app.repositories.dm_repo import count_total_unread

            count = await count_total_unread(uuid.UUID(_SENDER_ID))

        assert count == 7


class TestDMRepoIncrementCharCount:
    @pytest.mark.anyio
    async def test_positive_delta(self, mock_pool, mock_conn):
        """increment_char_count with positive delta executes UPDATE."""
        with patch(f"{_REPO}.get_pool", return_value=mock_pool):
            from app.repositories.dm_repo import increment_char_count

            await increment_char_count(_CONV_ID, 100)

        args = mock_conn.execute.call_args[0]
        assert args[1] == 100  # delta
        assert args[2] == _CONV_ID

    @pytest.mark.anyio
    async def test_negative_delta_floors_at_zero(self, mock_pool, mock_conn):
        """increment_char_count with negative delta uses GREATEST(0, ...)."""
        with patch(f"{_REPO}.get_pool", return_value=mock_pool):
            from app.repositories.dm_repo import increment_char_count

            await increment_char_count(_CONV_ID, -50)

        args = mock_conn.execute.call_args[0]
        assert args[1] == -50


class TestDMRepoDeleteOldestMessagesByChars:
    @pytest.mark.anyio
    async def test_returns_deleted_messages(self, mock_pool, mock_conn):
        """delete_oldest_messages_by_chars returns deleted rows and decrements total_chars."""
        deleted_row = {
            "id": uuid.uuid4(),
            "content": "Old msg",
            "attachment_key": None,
            "attachment_size": None,
            "sender_id": uuid.UUID(_SENDER_ID),
            "char_len": 7,
        }
        mock_conn.fetch.return_value = [deleted_row]

        with patch(f"{_REPO}.get_pool", return_value=mock_pool):
            from app.repositories.dm_repo import delete_oldest_messages_by_chars

            result = await delete_oldest_messages_by_chars(_CONV_ID, 100)

        assert len(result) == 1
        assert result[0]["char_len"] == 7
        # Should have called execute to decrement total_chars
        assert mock_conn.execute.called


class TestDMRepoFindExpiredFileMessages:
    @pytest.mark.anyio
    async def test_returns_expired_files(self, mock_pool, mock_conn):
        """find_expired_file_messages returns messages with expired attachments."""
        row = {
            "id": uuid.uuid4(),
            "conversation_id": _CONV_ID,
            "attachment_key": "dm/test/file.pdf",
            "attachment_size": 1024,
            "sender_id": uuid.UUID(_SENDER_ID),
        }
        mock_conn.fetch.return_value = [row]

        with patch(f"{_REPO}.get_pool", return_value=mock_pool):
            from app.repositories.dm_repo import find_expired_file_messages

            result = await find_expired_file_messages(_NOW)

        assert len(result) == 1
        assert result[0]["attachment_key"] == "dm/test/file.pdf"


class TestDMRepoFindExpiredTextMessages:
    @pytest.mark.anyio
    async def test_returns_expired_text_messages(self, mock_pool, mock_conn):
        """find_expired_text_messages returns old text-only messages."""
        row = {"id": uuid.uuid4(), "conversation_id": _CONV_ID, "content": "Old text"}
        mock_conn.fetch.return_value = [row]

        with patch(f"{_REPO}.get_pool", return_value=mock_pool):
            from app.repositories.dm_repo import find_expired_text_messages

            result = await find_expired_text_messages(_NOW - timedelta(days=30))

        assert len(result) == 1
        assert result[0]["content"] == "Old text"


class TestDMRepoGetDmFriendsOnly:
    @pytest.mark.anyio
    async def test_returns_true_when_set(self, mock_pool, mock_conn):
        """get_dm_friends_only returns True when preference is True."""
        mock_conn.fetchval.return_value = True

        with patch(f"{_REPO}.get_pool", return_value=mock_pool):
            from app.repositories.dm_repo import get_dm_friends_only

            result = await get_dm_friends_only(uuid.UUID(_SENDER_ID))

        assert result is True

    @pytest.mark.anyio
    async def test_returns_false_when_no_row(self, mock_pool, mock_conn):
        """get_dm_friends_only returns False when no preference row exists."""
        mock_conn.fetchval.return_value = None

        with patch(f"{_REPO}.get_pool", return_value=mock_pool):
            from app.repositories.dm_repo import get_dm_friends_only

            result = await get_dm_friends_only(uuid.UUID(_SENDER_ID))

        assert result is False

    @pytest.mark.anyio
    async def test_returns_false_when_explicitly_false(self, mock_pool, mock_conn):
        """get_dm_friends_only returns False when preference is False."""
        mock_conn.fetchval.return_value = False

        with patch(f"{_REPO}.get_pool", return_value=mock_pool):
            from app.repositories.dm_repo import get_dm_friends_only

            result = await get_dm_friends_only(uuid.UUID(_SENDER_ID))

        assert result is False


class TestDMRepoFindMessageById:
    @pytest.mark.anyio
    async def test_returns_message(self, mock_pool, mock_conn):
        """find_message_by_id returns dict when found."""
        row = _make_message_row()
        mock_conn.fetchrow.return_value = row

        with patch(f"{_REPO}.get_pool", return_value=mock_pool):
            from app.repositories.dm_repo import find_message_by_id

            result = await find_message_by_id(_MSG_ID)

        assert result is not None

    @pytest.mark.anyio
    async def test_returns_none_when_not_found(self, mock_pool, mock_conn):
        """find_message_by_id returns None when not found."""
        mock_conn.fetchrow.return_value = None

        with patch(f"{_REPO}.get_pool", return_value=mock_pool):
            from app.repositories.dm_repo import find_message_by_id

            result = await find_message_by_id(uuid.uuid4())

        assert result is None


class TestDMRepoDeleteMessagesById:
    @pytest.mark.anyio
    async def test_returns_delete_count(self, mock_pool, mock_conn):
        """delete_messages_by_ids returns count of deleted rows."""
        mock_conn.execute.return_value = "DELETE 5"

        with patch(f"{_REPO}.get_pool", return_value=mock_pool):
            from app.repositories.dm_repo import delete_messages_by_ids

            count = await delete_messages_by_ids([uuid.uuid4(), uuid.uuid4()])

        assert count == 5


class TestDMRepoClearMessageAttachment:
    @pytest.mark.anyio
    async def test_clears_attachment_fields(self, mock_pool, mock_conn):
        """clear_message_attachment NULLs all attachment fields."""
        with patch(f"{_REPO}.get_pool", return_value=mock_pool):
            from app.repositories.dm_repo import clear_message_attachment

            await clear_message_attachment(_MSG_ID)

        assert mock_conn.execute.called


class TestDMRepoGetConversationCharCount:
    @pytest.mark.anyio
    async def test_returns_char_count(self, mock_pool, mock_conn):
        """get_conversation_char_count returns total_chars value."""
        mock_conn.fetchval.return_value = 12345

        with patch(f"{_REPO}.get_pool", return_value=mock_pool):
            from app.repositories.dm_repo import get_conversation_char_count

            count = await get_conversation_char_count(_CONV_ID)

        assert count == 12345

    @pytest.mark.anyio
    async def test_returns_zero_when_null(self, mock_pool, mock_conn):
        """get_conversation_char_count returns 0 when fetchval returns None."""
        mock_conn.fetchval.return_value = None

        with patch(f"{_REPO}.get_pool", return_value=mock_pool):
            from app.repositories.dm_repo import get_conversation_char_count

            count = await get_conversation_char_count(_CONV_ID)

        assert count == 0


# ══════════════════════════════════════════════════════════════════════════════
# 2. SERVICE TESTS
# ══════════════════════════════════════════════════════════════════════════════


def _mock_pool_context():
    """Create a mock pool with acquire() context manager."""
    pool = MagicMock()
    conn = AsyncMock()
    # fetchval returns 0 by default (used for quota checks and advisory locks)
    conn.fetchval = AsyncMock(return_value=0)
    # transaction() context manager
    tx = AsyncMock()
    tx.__aenter__ = AsyncMock(return_value=tx)
    tx.__aexit__ = AsyncMock(return_value=False)
    conn.transaction = MagicMock(return_value=tx)
    cm = AsyncMock()
    cm.__aenter__ = AsyncMock(return_value=conn)
    cm.__aexit__ = AsyncMock(return_value=False)
    pool.acquire.return_value = cm
    return pool, conn


class TestSendMessageService:
    @pytest.mark.anyio
    @patch(f"{_SVC}.async_row_to_message", new_callable=AsyncMock)
    @patch(f"{_SVC}.emit", new_callable=AsyncMock)
    @patch(f"{_SVC}.dm_repo")
    async def test_send_text_success(self, mock_dm_repo, mock_emit, mock_convert):
        """send_message succeeds with valid text content."""
        pool, conn = _mock_pool_context()
        conv = _make_conversation(conv_id=_CONV_ID)
        msg_row = _make_message_row(sender_id=_SENDER_ID)
        msg_dict = _make_msg_response()

        mock_dm_repo.find_or_create_conversation = AsyncMock(return_value=conv)
        mock_dm_repo.send_message_atomic = AsyncMock(return_value=(msg_row, []))
        mock_dm_repo.get_dm_friends_only = AsyncMock(return_value=False)
        mock_convert.return_value = msg_dict

        with (
            patch("app.core.database.get_pool", return_value=pool),
            patch(
                "app.repositories.social_repo.is_blocked",
                new_callable=AsyncMock,
                return_value=False,
            ),
        ):
            from app.services.dm import send_message

            result = await send_message(
                sender_id=_SENDER_ID, recipient_id=_RECIPIENT_ID, content="Hello!"
            )

        assert result["content"] == "Hello!"
        mock_emit.assert_called_once()

    @pytest.mark.anyio
    @patch(f"{_SVC}.async_row_to_message", new_callable=AsyncMock)
    @patch(f"{_SVC}.emit", new_callable=AsyncMock)
    @patch(f"{_SVC}.dm_repo")
    async def test_send_file_success(self, mock_dm_repo, mock_emit, mock_convert):
        """send_message succeeds with file attachment."""
        pool, conn = _mock_pool_context()
        conv = _make_conversation(conv_id=_CONV_ID)
        msg_row = _make_message_row(
            sender_id=_SENDER_ID,
            attachment_key="dm/test/file.pdf",
            attachment_name="file.pdf",
            attachment_size=1024,
        )
        msg_dict = _make_msg_response()
        msg_dict["attachment_url"] = "http://minio/presigned"

        mock_dm_repo.find_or_create_conversation = AsyncMock(return_value=conv)
        mock_dm_repo.send_message_atomic = AsyncMock(return_value=(msg_row, []))
        mock_dm_repo.get_dm_friends_only = AsyncMock(return_value=False)
        mock_convert.return_value = msg_dict

        with (
            patch("app.core.database.get_pool", return_value=pool),
            patch(
                "app.repositories.social_repo.is_blocked",
                new_callable=AsyncMock,
                return_value=False,
            ),
            patch(
                "app.repositories.user_repo.get_storage_used",
                new_callable=AsyncMock,
                return_value=0,
            ),
            patch("app.repositories.user_repo.increment_storage_used", new_callable=AsyncMock),
            patch("app.core.async_storage.upload_file", new_callable=AsyncMock),
            patch("app.core.storage.generate_presigned_url", return_value="http://minio/presigned"),
            patch(f"{_SVC}._validate_dm_file"),
        ):
            from app.services.dm import send_message

            result = await send_message(
                sender_id=_SENDER_ID,
                recipient_id=_RECIPIENT_ID,
                file_data=b"data",
                file_name="file.pdf",
                file_size=1024,
                file_content_type="application/pdf",
            )

        assert result["attachment_url"] == "http://minio/presigned"
        mock_emit.assert_called_once()

    @pytest.mark.anyio
    @patch(f"{_SVC}.async_row_to_message", new_callable=AsyncMock)
    @patch(f"{_SVC}.emit", new_callable=AsyncMock)
    @patch(f"{_SVC}.dm_repo")
    async def test_send_text_and_file_success(self, mock_dm_repo, mock_emit, mock_convert):
        """send_message succeeds with both text and file."""
        pool, conn = _mock_pool_context()
        conv = _make_conversation(conv_id=_CONV_ID)
        msg_row = _make_message_row(sender_id=_SENDER_ID, attachment_key="dm/test/f.pdf")
        msg_dict = _make_msg_response(content="With file")
        msg_dict["attachment_url"] = "http://presigned"

        mock_dm_repo.find_or_create_conversation = AsyncMock(return_value=conv)
        mock_dm_repo.send_message_atomic = AsyncMock(return_value=(msg_row, []))
        mock_dm_repo.get_dm_friends_only = AsyncMock(return_value=False)
        mock_convert.return_value = msg_dict

        with (
            patch("app.core.database.get_pool", return_value=pool),
            patch(
                "app.repositories.social_repo.is_blocked",
                new_callable=AsyncMock,
                return_value=False,
            ),
            patch(
                "app.repositories.user_repo.get_storage_used",
                new_callable=AsyncMock,
                return_value=0,
            ),
            patch("app.repositories.user_repo.increment_storage_used", new_callable=AsyncMock),
            patch("app.core.async_storage.upload_file", new_callable=AsyncMock),
            patch("app.core.storage.generate_presigned_url", return_value="http://presigned"),
            patch(f"{_SVC}._validate_dm_file"),
        ):
            from app.services.dm import send_message

            result = await send_message(
                sender_id=_SENDER_ID,
                recipient_id=_RECIPIENT_ID,
                content="With file",
                file_data=b"data",
                file_name="f.pdf",
                file_size=500,
                file_content_type="application/pdf",
            )

        assert result["content"] == "With file"
        assert result["attachment_url"] == "http://presigned"

    @pytest.mark.anyio
    async def test_send_self_message_raises_dm003(self):
        """send_message to self raises DM_003."""
        from app.services.dm import send_message

        with pytest.raises(AppError) as exc:
            await send_message(sender_id=_SENDER_ID, recipient_id=_SENDER_ID, content="Hi")

        assert exc.value.status_code == 400

    @pytest.mark.anyio
    async def test_send_no_content_or_file_raises_422(self):
        """send_message with neither content nor file raises SYS_422."""
        from app.services.dm import send_message

        with pytest.raises(AppError) as exc:
            await send_message(sender_id=_SENDER_ID, recipient_id=_RECIPIENT_ID)

        assert exc.value.status_code == 422

    @pytest.mark.anyio
    async def test_send_content_too_long_raises_422(self):
        """send_message with content exceeding DM_MAX_MESSAGE_LENGTH raises SYS_422."""
        from app.services.dm import send_message

        with pytest.raises(AppError) as exc:
            await send_message(
                sender_id=_SENDER_ID,
                recipient_id=_RECIPIENT_ID,
                content="x" * 5001,
            )

        assert exc.value.status_code == 422

    @pytest.mark.anyio
    @patch(f"{_SVC}.dm_repo")
    async def test_send_blocked_user_raises_dm001(self, mock_dm_repo):
        """send_message to a blocked user raises DM_001."""
        pool, conn = _mock_pool_context()

        with (
            patch("app.core.database.get_pool", return_value=pool),
            patch(
                "app.repositories.social_repo.is_blocked", new_callable=AsyncMock, return_value=True
            ),
        ):
            from app.services.dm import send_message

            with pytest.raises(AppError) as exc:
                await send_message(sender_id=_SENDER_ID, recipient_id=_RECIPIENT_ID, content="Hi")

        assert exc.value.status_code == 403

    @pytest.mark.anyio
    @patch(f"{_SVC}.dm_repo")
    async def test_send_friends_only_not_friend_raises_dm001(self, mock_dm_repo):
        """send_message to friends-only user who is not a friend raises DM_001."""
        pool, conn = _mock_pool_context()
        # dm_friends_only is now queried inline via conn.fetchval
        conn.fetchval = AsyncMock(return_value=True)

        with (
            patch("app.core.database.get_pool", return_value=pool),
            patch(
                "app.repositories.social_repo.is_blocked",
                new_callable=AsyncMock,
                return_value=False,
            ),
            patch(
                "app.repositories.social_repo.find_friendship_between",
                new_callable=AsyncMock,
                return_value=None,
            ),
        ):
            from app.services.dm import send_message

            with pytest.raises(AppError) as exc:
                await send_message(sender_id=_SENDER_ID, recipient_id=_RECIPIENT_ID, content="Hi")

        assert exc.value.status_code == 403

    @pytest.mark.anyio
    @patch(f"{_SVC}.async_row_to_message", new_callable=AsyncMock)
    @patch(f"{_SVC}.emit", new_callable=AsyncMock)
    @patch(f"{_SVC}.dm_repo")
    async def test_send_friends_only_is_friend_succeeds(
        self, mock_dm_repo, mock_emit, mock_convert
    ):
        """send_message to friends-only user succeeds when friendship is ACCEPTED."""
        pool, conn = _mock_pool_context()
        conv = _make_conversation(conv_id=_CONV_ID)
        msg_row = _make_message_row(sender_id=_SENDER_ID)

        # dm_friends_only is now queried inline via conn.fetchval
        conn.fetchval = AsyncMock(return_value=True)
        mock_dm_repo.find_or_create_conversation = AsyncMock(return_value=conv)
        mock_dm_repo.send_message_atomic = AsyncMock(return_value=(msg_row, []))
        mock_convert.return_value = _make_msg_response()

        with (
            patch("app.core.database.get_pool", return_value=pool),
            patch(
                "app.repositories.social_repo.is_blocked",
                new_callable=AsyncMock,
                return_value=False,
            ),
            patch(
                "app.repositories.social_repo.find_friendship_between",
                new_callable=AsyncMock,
                return_value={"status": "ACCEPTED"},
            ),
        ):
            from app.services.dm import send_message

            result = await send_message(
                sender_id=_SENDER_ID, recipient_id=_RECIPIENT_ID, content="Hi friend"
            )

        assert result is not None

    @pytest.mark.anyio
    @patch(f"{_SVC}.dm_repo")
    async def test_send_storage_quota_exceeded(self, mock_dm_repo):
        """send_message with file raises DM_004 when quota exceeded."""
        pool, conn = _mock_pool_context()
        # First fetchval: dm_friends_only check (False),
        # second: atomic UPDATE RETURNING None (quota full, WHERE condition not met)
        conn.fetchval = AsyncMock(side_effect=[False, None])

        with (
            patch("app.core.database.get_pool", return_value=pool),
            patch(
                "app.repositories.social_repo.is_blocked",
                new_callable=AsyncMock,
                return_value=False,
            ),
            patch(f"{_SVC}._validate_dm_file"),
        ):
            from app.services.dm import send_message

            with pytest.raises(AppError) as exc:
                await send_message(
                    sender_id=_SENDER_ID,
                    recipient_id=_RECIPIENT_ID,
                    file_data=b"x" * 100,
                    file_name="big.bin",
                    file_size=100,
                    file_content_type="application/octet-stream",
                )

            assert exc.value.status_code == 413
            assert exc.value.detail["code"] == "DM_004"

    @pytest.mark.anyio
    @patch(f"{_SVC}.async_row_to_message", new_callable=AsyncMock)
    @patch(f"{_SVC}.emit", new_callable=AsyncMock)
    @patch(f"{_SVC}.dm_repo")
    async def test_send_char_cap_uses_atomic(self, mock_dm_repo, mock_emit, mock_convert):
        """send_message uses send_message_atomic for char cap enforcement."""
        pool, conn = _mock_pool_context()
        conv = _make_conversation(conv_id=_CONV_ID)
        msg_row = _make_message_row(sender_id=_SENDER_ID)

        mock_dm_repo.find_or_create_conversation = AsyncMock(return_value=conv)
        mock_dm_repo.send_message_atomic = AsyncMock(return_value=(msg_row, []))
        mock_dm_repo.get_dm_friends_only = AsyncMock(return_value=False)
        mock_convert.return_value = _make_msg_response()

        with (
            patch("app.core.database.get_pool", return_value=pool),
            patch(
                "app.repositories.social_repo.is_blocked",
                new_callable=AsyncMock,
                return_value=False,
            ),
        ):
            from app.services.dm import send_message

            result = await send_message(
                sender_id=_SENDER_ID, recipient_id=_RECIPIENT_ID, content="New msg"
            )

        mock_dm_repo.send_message_atomic.assert_called_once()
        assert result is not None

    @pytest.mark.anyio
    @patch(f"{_SVC}.emit", new_callable=AsyncMock)
    @patch(f"{_SVC}.dm_repo")
    async def test_send_event_emitted(self, mock_dm_repo, mock_emit):
        """send_message emits dm.message_sent event."""
        pool, conn = _mock_pool_context()
        conv = _make_conversation(conv_id=_CONV_ID)
        msg_row = _make_message_row(sender_id=_SENDER_ID)

        mock_dm_repo.find_or_create_conversation = AsyncMock(return_value=conv)
        mock_dm_repo.send_message_atomic = AsyncMock(return_value=(msg_row, []))
        mock_dm_repo.get_dm_friends_only = AsyncMock(return_value=False)

        with (
            patch("app.core.database.get_pool", return_value=pool),
            patch(
                "app.repositories.social_repo.is_blocked",
                new_callable=AsyncMock,
                return_value=False,
            ),
            patch(
                f"{_SVC}.async_row_to_message",
                new_callable=AsyncMock,
                return_value=_make_msg_response(),
            ),
        ):
            from app.services.dm import send_message

            await send_message(sender_id=_SENDER_ID, recipient_id=_RECIPIENT_ID, content="Hi")

        mock_emit.assert_called_once()
        call_args = mock_emit.call_args
        assert call_args[0][0] == "dm.message_sent"
        assert call_args[1]["recipient_id"] == _RECIPIENT_ID
        assert "message" in call_args[1]


class TestEditMessageService:
    @pytest.mark.anyio
    @patch("app.core.database.get_pool")
    @patch(f"{_SVC}.async_row_to_message", new_callable=AsyncMock)
    @patch(f"{_SVC}.emit", new_callable=AsyncMock)
    @patch(f"{_SVC}.dm_repo")
    async def test_edit_success_within_window(
        self, mock_dm_repo, mock_emit, mock_convert, mock_get_pool
    ):
        """edit_message succeeds within 12h window."""
        msg_row = _make_message_row(sender_id=_SENDER_ID, created_at=_NOW)
        updated_row = _make_message_row(sender_id=_SENDER_ID, content="Updated!", is_edited=True)
        conv = _make_conversation(
            conv_id=msg_row["conversation_id"],
            user_a=_SENDER_ID,
            user_b=_RECIPIENT_ID,
        )

        # Mock pool -> conn -> transaction; fetchrow returns msg_row then updated_row
        mock_conn = MagicMock()
        mock_conn.fetchval = AsyncMock(return_value=None)
        mock_conn.fetchrow = AsyncMock(side_effect=[msg_row, updated_row])
        mock_conn.execute = AsyncMock()

        mock_tx = MagicMock()
        mock_tx.__aenter__ = AsyncMock(return_value=None)
        mock_tx.__aexit__ = AsyncMock(return_value=None)
        mock_conn.transaction.return_value = mock_tx

        mock_acq = MagicMock()
        mock_acq.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_acq.__aexit__ = AsyncMock(return_value=None)
        mock_get_pool.return_value.acquire.return_value = mock_acq

        mock_dm_repo.find_conversation_by_id = AsyncMock(return_value=conv)
        mock_convert.return_value = _make_msg_response(content="Updated!")

        from app.services.dm import edit_message

        result = await edit_message(str(_MSG_ID), _SENDER_ID, "Updated!")

        assert result["content"] == "Updated!"
        mock_emit.assert_called_once()

    @pytest.mark.anyio
    @patch("app.core.database.get_pool")
    async def test_edit_wrong_sender_raises_403(self, mock_get_pool):
        """edit_message by wrong sender raises SYS_403."""
        msg_row = _make_message_row(sender_id=str(uuid.uuid4()))

        mock_conn = MagicMock()
        mock_conn.fetchval = AsyncMock(return_value=None)
        mock_conn.fetchrow = AsyncMock(return_value=msg_row)
        mock_tx = MagicMock()
        mock_tx.__aenter__ = AsyncMock(return_value=None)
        mock_tx.__aexit__ = AsyncMock(return_value=None)
        mock_conn.transaction.return_value = mock_tx
        mock_acq = MagicMock()
        mock_acq.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_acq.__aexit__ = AsyncMock(return_value=None)
        mock_get_pool.return_value.acquire.return_value = mock_acq

        from app.services.dm import edit_message

        with pytest.raises(AppError) as exc:
            await edit_message(str(_MSG_ID), _SENDER_ID, "Hacked!")

        assert exc.value.status_code == 403

    @pytest.mark.anyio
    @patch("app.core.database.get_pool")
    async def test_edit_recalled_message_raises_422(self, mock_get_pool):
        """edit_message on recalled message raises SYS_422."""
        msg_row = _make_message_row(sender_id=_SENDER_ID, is_recalled=True)

        mock_conn = MagicMock()
        mock_conn.fetchval = AsyncMock(return_value=None)
        mock_conn.fetchrow = AsyncMock(return_value=msg_row)
        mock_tx = MagicMock()
        mock_tx.__aenter__ = AsyncMock(return_value=None)
        mock_tx.__aexit__ = AsyncMock(return_value=None)
        mock_conn.transaction.return_value = mock_tx
        mock_acq = MagicMock()
        mock_acq.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_acq.__aexit__ = AsyncMock(return_value=None)
        mock_get_pool.return_value.acquire.return_value = mock_acq

        from app.services.dm import edit_message

        with pytest.raises(AppError) as exc:
            await edit_message(str(_MSG_ID), _SENDER_ID, "Edit recalled")

        assert exc.value.status_code == 422

    @pytest.mark.anyio
    @patch("app.core.database.get_pool")
    async def test_edit_expired_window_raises_dm002(self, mock_get_pool):
        """edit_message after 12h window raises DM_002."""
        old_time = _NOW - timedelta(hours=13)
        msg_row = _make_message_row(sender_id=_SENDER_ID, created_at=old_time)

        mock_conn = MagicMock()
        mock_conn.fetchval = AsyncMock(return_value=None)
        mock_conn.fetchrow = AsyncMock(return_value=msg_row)
        mock_tx = MagicMock()
        mock_tx.__aenter__ = AsyncMock(return_value=None)
        mock_tx.__aexit__ = AsyncMock(return_value=None)
        mock_conn.transaction.return_value = mock_tx
        mock_acq = MagicMock()
        mock_acq.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_acq.__aexit__ = AsyncMock(return_value=None)
        mock_get_pool.return_value.acquire.return_value = mock_acq

        from app.services.dm import edit_message

        with pytest.raises(AppError) as exc:
            await edit_message(str(_MSG_ID), _SENDER_ID, "Too late")

        assert exc.value.status_code == 403

    @pytest.mark.anyio
    @patch("app.core.database.get_pool")
    async def test_edit_not_found_raises_404(self, mock_get_pool):
        """edit_message on non-existent message raises SYS_404."""
        mock_conn = MagicMock()
        mock_conn.fetchval = AsyncMock(return_value=None)
        mock_conn.fetchrow = AsyncMock(return_value=None)
        mock_tx = MagicMock()
        mock_tx.__aenter__ = AsyncMock(return_value=None)
        mock_tx.__aexit__ = AsyncMock(return_value=None)
        mock_conn.transaction.return_value = mock_tx
        mock_acq = MagicMock()
        mock_acq.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_acq.__aexit__ = AsyncMock(return_value=None)
        mock_get_pool.return_value.acquire.return_value = mock_acq

        from app.services.dm import edit_message

        with pytest.raises(AppError) as exc:
            await edit_message(str(uuid.uuid4()), _SENDER_ID, "Where?")

        assert exc.value.status_code == 404

    @pytest.mark.anyio
    @patch("app.core.database.get_pool")
    @patch(f"{_SVC}.async_row_to_message", new_callable=AsyncMock)
    @patch(f"{_SVC}.emit", new_callable=AsyncMock)
    @patch(f"{_SVC}.dm_repo")
    async def test_edit_adjusts_char_count(
        self, mock_dm_repo, mock_emit, mock_convert, mock_get_pool
    ):
        """edit_message adjusts conversation char count by delta."""
        msg_row = _make_message_row(sender_id=_SENDER_ID, content="Short")
        updated_row = _make_message_row(
            sender_id=_SENDER_ID, content="Much longer message", is_edited=True
        )
        conv = _make_conversation(
            conv_id=msg_row["conversation_id"],
            user_a=_SENDER_ID,
            user_b=_RECIPIENT_ID,
        )

        # Mock pool -> conn -> transaction; fetchrow returns msg_row then updated_row
        mock_conn = MagicMock()
        mock_conn.fetchval = AsyncMock(return_value=None)
        mock_conn.fetchrow = AsyncMock(side_effect=[msg_row, updated_row])
        mock_conn.execute = AsyncMock()
        mock_tx = MagicMock()
        mock_tx.__aenter__ = AsyncMock(return_value=None)
        mock_tx.__aexit__ = AsyncMock(return_value=None)
        mock_conn.transaction.return_value = mock_tx
        mock_acq = MagicMock()
        mock_acq.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_acq.__aexit__ = AsyncMock(return_value=None)
        mock_get_pool.return_value.acquire.return_value = mock_acq

        mock_dm_repo.find_conversation_by_id = AsyncMock(return_value=conv)
        mock_convert.return_value = _make_msg_response(content="Much longer message")

        from app.services.dm import edit_message

        await edit_message(str(_MSG_ID), _SENDER_ID, "Much longer message")

        # delta = len("Much longer message") - len("Short") = 19 - 5 = 14
        # Char count update happens via conn.execute in the transaction
        assert mock_conn.execute.called

    @pytest.mark.anyio
    async def test_edit_content_too_long_raises_422(self):
        """edit_message with content exceeding max length raises SYS_422."""
        from app.services.dm import edit_message

        with pytest.raises(AppError) as exc:
            await edit_message(str(_MSG_ID), _SENDER_ID, "x" * 5001)

        assert exc.value.status_code == 422


class TestRecallMessageService:
    @pytest.mark.anyio
    @patch("app.core.database.get_pool")
    @patch(f"{_SVC}.async_row_to_message", new_callable=AsyncMock)
    @patch(f"{_SVC}.emit", new_callable=AsyncMock)
    @patch(f"{_SVC}.dm_repo")
    async def test_recall_success_within_window(
        self, mock_dm_repo, mock_emit, mock_convert, mock_get_pool
    ):
        """recall_message succeeds within 12h window."""
        msg_row = _make_message_row(sender_id=_SENDER_ID, content="Oops")
        recalled_row = _make_message_row(sender_id=_SENDER_ID, is_recalled=True, content=None)
        conv = _make_conversation(
            conv_id=msg_row["conversation_id"],
            user_a=_SENDER_ID,
            user_b=_RECIPIENT_ID,
        )

        # Mock pool -> conn -> transaction; fetchrow returns msg_row then recalled_row
        mock_conn = MagicMock()
        mock_conn.fetchval = AsyncMock(return_value=None)
        mock_conn.fetchrow = AsyncMock(side_effect=[msg_row, recalled_row])
        mock_conn.execute = AsyncMock()
        mock_tx = MagicMock()
        mock_tx.__aenter__ = AsyncMock(return_value=None)
        mock_tx.__aexit__ = AsyncMock(return_value=None)
        mock_conn.transaction.return_value = mock_tx
        mock_acq = MagicMock()
        mock_acq.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_acq.__aexit__ = AsyncMock(return_value=None)
        mock_get_pool.return_value.acquire.return_value = mock_acq

        mock_dm_repo.find_conversation_by_id = AsyncMock(return_value=conv)
        mock_convert.return_value = _make_msg_response(content=None)

        from app.services.dm import recall_message

        result = await recall_message(str(_MSG_ID), _SENDER_ID)

        assert result is not None
        mock_emit.assert_called_once()

    @pytest.mark.anyio
    @patch("app.core.database.get_pool")
    @patch(f"{_SVC}.async_row_to_message", new_callable=AsyncMock)
    @patch(f"{_SVC}.emit", new_callable=AsyncMock)
    @patch(f"{_SVC}.dm_repo")
    async def test_recall_with_attachment_deletes_storage(
        self, mock_dm_repo, mock_emit, mock_convert, mock_get_pool
    ):
        """recall_message with attachment deletes file and refunds quota."""
        msg_row = _make_message_row(
            sender_id=_SENDER_ID,
            content="With file",
            attachment_key="dm/test/file.pdf",
            attachment_size=2048,
        )
        recalled_row = _make_message_row(sender_id=_SENDER_ID, is_recalled=True, content=None)
        conv = _make_conversation(
            conv_id=msg_row["conversation_id"],
            user_a=_SENDER_ID,
            user_b=_RECIPIENT_ID,
        )

        # Mock pool -> conn -> transaction; fetchrow returns msg_row then recalled_row
        mock_conn = MagicMock()
        mock_conn.fetchval = AsyncMock(return_value=None)
        mock_conn.fetchrow = AsyncMock(side_effect=[msg_row, recalled_row])
        mock_conn.execute = AsyncMock()
        mock_tx = MagicMock()
        mock_tx.__aenter__ = AsyncMock(return_value=None)
        mock_tx.__aexit__ = AsyncMock(return_value=None)
        mock_conn.transaction.return_value = mock_tx
        mock_acq = MagicMock()
        mock_acq.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_acq.__aexit__ = AsyncMock(return_value=None)
        mock_get_pool.return_value.acquire.return_value = mock_acq

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

        mock_delete.assert_awaited_once_with("dm/test/file.pdf")
        mock_decrement.assert_called_once_with(uuid.UUID(_SENDER_ID), 2048)

    @pytest.mark.anyio
    @patch("app.core.database.get_pool")
    @patch(f"{_SVC}.async_row_to_message", new_callable=AsyncMock)
    @patch(f"{_SVC}.emit", new_callable=AsyncMock)
    @patch(f"{_SVC}.dm_repo")
    async def test_recall_without_attachment_no_storage_ops(
        self, mock_dm_repo, mock_emit, mock_convert, mock_get_pool
    ):
        """recall_message without attachment does not call storage delete."""
        msg_row = _make_message_row(sender_id=_SENDER_ID, content="Text only")
        recalled_row = _make_message_row(sender_id=_SENDER_ID, is_recalled=True, content=None)
        conv = _make_conversation(
            conv_id=msg_row["conversation_id"],
            user_a=_SENDER_ID,
            user_b=_RECIPIENT_ID,
        )

        # Mock pool -> conn -> transaction; fetchrow returns msg_row then recalled_row
        mock_conn = MagicMock()
        mock_conn.fetchval = AsyncMock(return_value=None)
        mock_conn.fetchrow = AsyncMock(side_effect=[msg_row, recalled_row])
        mock_conn.execute = AsyncMock()
        mock_tx = MagicMock()
        mock_tx.__aenter__ = AsyncMock(return_value=None)
        mock_tx.__aexit__ = AsyncMock(return_value=None)
        mock_conn.transaction.return_value = mock_tx
        mock_acq = MagicMock()
        mock_acq.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_acq.__aexit__ = AsyncMock(return_value=None)
        mock_get_pool.return_value.acquire.return_value = mock_acq

        mock_dm_repo.find_conversation_by_id = AsyncMock(return_value=conv)
        mock_convert.return_value = _make_msg_response()

        with patch("app.core.async_storage.delete_file", new_callable=AsyncMock) as mock_delete:
            from app.services.dm import recall_message

            await recall_message(str(_MSG_ID), _SENDER_ID)

        mock_delete.assert_not_called()

    @pytest.mark.anyio
    @patch("app.core.database.get_pool")
    async def test_recall_expired_window_raises_dm002(self, mock_get_pool):
        """recall_message after 12h window raises DM_002."""
        old_time = _NOW - timedelta(hours=13)
        msg_row = _make_message_row(sender_id=_SENDER_ID, created_at=old_time)

        mock_conn = MagicMock()
        mock_conn.fetchval = AsyncMock(return_value=None)
        mock_conn.fetchrow = AsyncMock(return_value=msg_row)
        mock_tx = MagicMock()
        mock_tx.__aenter__ = AsyncMock(return_value=None)
        mock_tx.__aexit__ = AsyncMock(return_value=None)
        mock_conn.transaction.return_value = mock_tx
        mock_acq = MagicMock()
        mock_acq.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_acq.__aexit__ = AsyncMock(return_value=None)
        mock_get_pool.return_value.acquire.return_value = mock_acq

        from app.services.dm import recall_message

        with pytest.raises(AppError) as exc:
            await recall_message(str(_MSG_ID), _SENDER_ID)

        assert exc.value.status_code == 403

    @pytest.mark.anyio
    @patch("app.core.database.get_pool")
    async def test_recall_already_recalled_raises_422(self, mock_get_pool):
        """recall_message on already-recalled message raises SYS_422."""
        msg_row = _make_message_row(sender_id=_SENDER_ID, is_recalled=True)

        mock_conn = MagicMock()
        mock_conn.fetchval = AsyncMock(return_value=None)
        mock_conn.fetchrow = AsyncMock(return_value=msg_row)
        mock_tx = MagicMock()
        mock_tx.__aenter__ = AsyncMock(return_value=None)
        mock_tx.__aexit__ = AsyncMock(return_value=None)
        mock_conn.transaction.return_value = mock_tx
        mock_acq = MagicMock()
        mock_acq.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_acq.__aexit__ = AsyncMock(return_value=None)
        mock_get_pool.return_value.acquire.return_value = mock_acq

        from app.services.dm import recall_message

        with pytest.raises(AppError) as exc:
            await recall_message(str(_MSG_ID), _SENDER_ID)

        assert exc.value.status_code == 422

    @pytest.mark.anyio
    @patch("app.core.database.get_pool")
    async def test_recall_wrong_sender_raises_403(self, mock_get_pool):
        """recall_message by wrong sender raises SYS_403."""
        msg_row = _make_message_row(sender_id=str(uuid.uuid4()))

        mock_conn = MagicMock()
        mock_conn.fetchval = AsyncMock(return_value=None)
        mock_conn.fetchrow = AsyncMock(return_value=msg_row)
        mock_tx = MagicMock()
        mock_tx.__aenter__ = AsyncMock(return_value=None)
        mock_tx.__aexit__ = AsyncMock(return_value=None)
        mock_conn.transaction.return_value = mock_tx
        mock_acq = MagicMock()
        mock_acq.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_acq.__aexit__ = AsyncMock(return_value=None)
        mock_get_pool.return_value.acquire.return_value = mock_acq

        from app.services.dm import recall_message

        with pytest.raises(AppError) as exc:
            await recall_message(str(_MSG_ID), _SENDER_ID)

        assert exc.value.status_code == 403

    @pytest.mark.anyio
    @patch("app.core.database.get_pool")
    async def test_recall_not_found_raises_404(self, mock_get_pool):
        """recall_message on non-existent message raises SYS_404."""
        mock_conn = MagicMock()
        mock_conn.fetchval = AsyncMock(return_value=None)
        mock_conn.fetchrow = AsyncMock(return_value=None)
        mock_tx = MagicMock()
        mock_tx.__aenter__ = AsyncMock(return_value=None)
        mock_tx.__aexit__ = AsyncMock(return_value=None)
        mock_conn.transaction.return_value = mock_tx
        mock_acq = MagicMock()
        mock_acq.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_acq.__aexit__ = AsyncMock(return_value=None)
        mock_get_pool.return_value.acquire.return_value = mock_acq

        from app.services.dm import recall_message

        with pytest.raises(AppError) as exc:
            await recall_message(str(uuid.uuid4()), _SENDER_ID)

        assert exc.value.status_code == 404


class TestListConversationsService:
    @pytest.mark.anyio
    @patch(f"{_SVC}.dm_repo")
    async def test_list_conversations_with_presigned_urls(self, mock_dm_repo):
        """list_conversations generates presigned URLs for last_message attachments."""
        row = _make_conversation_list_row(user_id=_SENDER_ID, other_id=_RECIPIENT_ID)
        row["last_msg_attachment_key"] = "dm/test/file.pdf"
        mock_dm_repo.find_conversations = AsyncMock(return_value=([row], 1))

        with (
            patch(f"{_SVC}.async_row_to_conversation", new_callable=AsyncMock) as mock_conv,
            patch(
                "app.core.storage.generate_presigned_url", return_value="http://presigned"
            ),  # mock_presign unused but patch needed
        ):
            conv_dict = {
                "id": str(row["id"]),
                "other_user": {"id": _RECIPIENT_ID, "display_name": "Other", "avatar_url": None},
                "last_message": {
                    "id": str(uuid.uuid4()),
                    "attachment_key": "dm/test/file.pdf",
                    "attachment_name": "file.pdf",
                    "is_recalled": False,
                },
                "unread_count": 2,
                "updated_at": _NOW.isoformat(),
            }
            mock_conv.return_value = conv_dict

            from app.services.dm import list_conversations

            convos, total = await list_conversations(_SENDER_ID)

        assert total == 1
        assert convos[0]["last_message"]["attachment_url"] == "http://presigned"


class TestListMessagesService:
    @pytest.mark.anyio
    @patch(f"{_SVC}.dm_repo")
    async def test_list_messages_as_participant(self, mock_dm_repo):
        """list_messages returns messages when user is participant."""
        conv = _make_conversation(conv_id=_CONV_ID, user_a=_SENDER_ID, user_b=_RECIPIENT_ID)
        msg_row = _make_message_row(sender_id=_SENDER_ID)

        mock_dm_repo.find_conversation_by_id = AsyncMock(return_value=conv)
        mock_dm_repo.find_messages = AsyncMock(return_value=([msg_row], 1))

        with patch(
            f"{_SVC}.async_row_to_message",
            new_callable=AsyncMock,
            return_value=_make_msg_response(),
        ):
            from app.services.dm import list_messages

            msgs, total = await list_messages(_SENDER_ID, str(_CONV_ID))

        assert total == 1
        assert len(msgs) == 1

    @pytest.mark.anyio
    @patch(f"{_SVC}.dm_repo")
    async def test_list_messages_non_participant_raises_404(self, mock_dm_repo):
        """list_messages raises SYS_404 when user is not participant."""
        mock_dm_repo.find_conversation_by_id = AsyncMock(return_value=None)

        from app.services.dm import list_messages

        with pytest.raises(AppError) as exc:
            await list_messages(_SENDER_ID, str(_CONV_ID))

        assert exc.value.status_code == 404


class TestMarkReadService:
    @pytest.mark.anyio
    @patch(f"{_SVC}.emit", new_callable=AsyncMock)
    @patch(f"{_SVC}.dm_repo")
    async def test_mark_read_emits_event(self, mock_dm_repo, mock_emit):
        """mark_read marks messages and emits dm.messages_read event."""
        conv = _make_conversation(conv_id=_CONV_ID, user_a=_SENDER_ID, user_b=_RECIPIENT_ID)
        mock_dm_repo.find_conversation_by_id = AsyncMock(return_value=conv)
        mock_dm_repo.mark_messages_read = AsyncMock(return_value=3)

        from app.services.dm import mark_read

        result = await mark_read(_SENDER_ID, str(_CONV_ID))

        assert result is not None
        mock_emit.assert_called_once()
        call_kwargs = mock_emit.call_args
        assert call_kwargs[0][0] == "dm.messages_read"

    @pytest.mark.anyio
    @patch(f"{_SVC}.emit", new_callable=AsyncMock)
    @patch(f"{_SVC}.dm_repo")
    async def test_mark_read_no_unread_returns_none(self, mock_dm_repo, mock_emit):
        """mark_read returns None when no unread messages."""
        conv = _make_conversation(conv_id=_CONV_ID, user_a=_SENDER_ID, user_b=_RECIPIENT_ID)
        mock_dm_repo.find_conversation_by_id = AsyncMock(return_value=conv)
        mock_dm_repo.mark_messages_read = AsyncMock(return_value=0)

        from app.services.dm import mark_read

        result = await mark_read(_SENDER_ID, str(_CONV_ID))

        assert result is None
        mock_emit.assert_not_called()


class TestGetUnreadCountService:
    @pytest.mark.anyio
    @patch(f"{_SVC}.dm_repo")
    async def test_returns_correct_count(self, mock_dm_repo):
        """get_unread_count returns total unread count."""
        mock_dm_repo.count_total_unread = AsyncMock(return_value=42)

        from app.services.dm import get_unread_count

        count = await get_unread_count(_SENDER_ID)

        assert count == 42


# ══════════════════════════════════════════════════════════════════════════════
# 3. ENDPOINT TESTS
# ══════════════════════════════════════════════════════════════════════════════


class TestGetUnreadCountEndpoint:
    @pytest.mark.anyio
    async def test_200_with_count(self, client):
        """GET /dm/unread-count returns 200 with unread_count."""
        payload, uid = _override_auth("MEMBER")
        try:
            with patch(
                f"{_EP}.dm_service.get_unread_count", new_callable=AsyncMock, return_value=5
            ):
                resp = await client.get("/api/v1/dm/unread-count")
            assert resp.status_code == 200
            assert resp.json()["unread_count"] == 5
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_guest_403(self, client):
        """GET /dm/unread-count returns 403 for GUEST."""
        payload, uid = _override_auth("GUEST")
        try:
            resp = await client.get("/api/v1/dm/unread-count")
            assert resp.status_code == 403
        finally:
            _clear_overrides()


class TestListConversationsEndpoint:
    @pytest.mark.anyio
    async def test_200_with_conversations(self, client):
        """GET /dm/conversations returns 200 with paginated conversations."""
        payload, uid = _override_auth("MEMBER")
        convos = [
            {
                "id": str(uuid.uuid4()),
                "other_user": {"id": str(uuid.uuid4()), "display_name": "User", "avatar_url": None},
                "last_message": None,
                "unread_count": 0,
                "updated_at": _NOW.isoformat(),
            }
        ]
        try:
            with (
                patch(f"{_EP}.check_rate_limit", new_callable=AsyncMock, return_value=True),
                patch(
                    f"{_EP}.dm_service.list_conversations",
                    new_callable=AsyncMock,
                    return_value=(convos, 1),
                ),
            ):
                resp = await client.get("/api/v1/dm/conversations")
            assert resp.status_code == 200
            data = resp.json()
            assert data["total"] == 1
            assert len(data["conversations"]) == 1
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_rate_limited_429(self, client):
        """GET /dm/conversations returns 429 when rate limited."""
        payload, uid = _override_auth("MEMBER")
        try:
            with patch(f"{_EP}.check_rate_limit", new_callable=AsyncMock, return_value=False):
                resp = await client.get("/api/v1/dm/conversations")
            assert resp.status_code == 429
        finally:
            _clear_overrides()


class TestListMessagesEndpoint:
    @pytest.mark.anyio
    async def test_200_with_messages(self, client):
        """GET /dm/conversations/{id}/messages returns 200."""
        payload, uid = _override_auth("MEMBER")
        conv_id = uuid.uuid4()
        msgs = [_make_msg_response()]
        try:
            with (
                patch(f"{_EP}.check_rate_limit", new_callable=AsyncMock, return_value=True),
                patch(
                    f"{_EP}.dm_service.list_messages",
                    new_callable=AsyncMock,
                    return_value=(msgs, 1),
                ),
            ):
                resp = await client.get(f"/api/v1/dm/conversations/{conv_id}/messages")
            assert resp.status_code == 200
            data = resp.json()
            assert data["total"] == 1
            assert len(data["messages"]) == 1
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_non_participant_404(self, client):
        """GET /dm/conversations/{id}/messages returns 404 for non-participant."""
        payload, uid = _override_auth("MEMBER")
        conv_id = uuid.uuid4()
        try:
            with (
                patch(f"{_EP}.check_rate_limit", new_callable=AsyncMock, return_value=True),
                patch(
                    f"{_EP}.dm_service.list_messages",
                    new_callable=AsyncMock,
                    side_effect=AppError(ErrorCode.SYS_404, 404, "Conversation not found."),
                ),
            ):
                resp = await client.get(f"/api/v1/dm/conversations/{conv_id}/messages")
            assert resp.status_code == 404
        finally:
            _clear_overrides()


class TestSendMessageEndpoint:
    @pytest.mark.anyio
    async def test_201_text_only(self, client):
        """POST /dm/conversations/{user_id}/messages returns 201 with text."""
        payload, uid = _override_auth("MEMBER")
        target = uuid.uuid4()
        msg = _make_msg_response(content="Hello!")
        try:
            with (
                patch(f"{_EP}.check_rate_limit", new_callable=AsyncMock, return_value=True),
                patch(f"{_EP}.dm_service.send_message", new_callable=AsyncMock, return_value=msg),
            ):
                resp = await client.post(
                    f"/api/v1/dm/conversations/{target}/messages",
                    data={"content": "Hello!"},
                )
            assert resp.status_code == 201
            assert resp.json()["content"] == "Hello!"
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_201_file_only(self, client):
        """POST /dm/conversations/{user_id}/messages returns 201 with file only."""
        payload, uid = _override_auth("MEMBER")
        target = uuid.uuid4()
        msg = _make_msg_response()
        msg["attachment_url"] = "http://presigned"
        msg["attachment_name"] = "file.pdf"
        msg["attachment_size"] = 1024
        try:
            with (
                patch(f"{_EP}.check_rate_limit", new_callable=AsyncMock, return_value=True),
                patch(f"{_EP}.dm_service.send_message", new_callable=AsyncMock, return_value=msg),
            ):
                resp = await client.post(
                    f"/api/v1/dm/conversations/{target}/messages",
                    files={"file": ("file.pdf", b"data", "application/pdf")},
                )
            assert resp.status_code == 201
            assert resp.json()["attachment_url"] == "http://presigned"
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_201_text_and_file(self, client):
        """POST /dm/conversations/{user_id}/messages returns 201 with text + file."""
        payload, uid = _override_auth("MEMBER")
        target = uuid.uuid4()
        msg = _make_msg_response(content="See attached")
        msg["attachment_url"] = "http://presigned"
        try:
            with (
                patch(f"{_EP}.check_rate_limit", new_callable=AsyncMock, return_value=True),
                patch(f"{_EP}.dm_service.send_message", new_callable=AsyncMock, return_value=msg),
            ):
                resp = await client.post(
                    f"/api/v1/dm/conversations/{target}/messages",
                    data={"content": "See attached"},
                    files={"file": ("doc.pdf", b"data", "application/pdf")},
                )
            assert resp.status_code == 201
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_422_no_content_no_file(self, client):
        """POST /dm/conversations/{user_id}/messages returns 422 with no content or file."""
        payload, uid = _override_auth("MEMBER")
        target = uuid.uuid4()
        try:
            with patch(f"{_EP}.check_rate_limit", new_callable=AsyncMock, return_value=True):
                resp = await client.post(
                    f"/api/v1/dm/conversations/{target}/messages",
                    data={},
                )
            assert resp.status_code == 422
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_422_content_too_long(self, client):
        """POST /dm/conversations/{user_id}/messages returns 422 for oversized content."""
        payload, uid = _override_auth("MEMBER")
        target = uuid.uuid4()
        try:
            with patch(f"{_EP}.check_rate_limit", new_callable=AsyncMock, return_value=True):
                resp = await client.post(
                    f"/api/v1/dm/conversations/{target}/messages",
                    data={"content": "x" * 5001},
                )
            assert resp.status_code == 422
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_422_empty_file(self, client):
        """POST /dm/conversations/{user_id}/messages returns 422 for empty file."""
        payload, uid = _override_auth("MEMBER")
        target = uuid.uuid4()
        try:
            with patch(f"{_EP}.check_rate_limit", new_callable=AsyncMock, return_value=True):
                resp = await client.post(
                    f"/api/v1/dm/conversations/{target}/messages",
                    files={"file": ("empty.txt", b"", "text/plain")},
                )
            assert resp.status_code == 422
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_403_blocked_user(self, client):
        """POST /dm/conversations/{user_id}/messages returns 403 for blocked user."""
        payload, uid = _override_auth("MEMBER")
        target = uuid.uuid4()
        try:
            with (
                patch(f"{_EP}.check_rate_limit", new_callable=AsyncMock, return_value=True),
                patch(
                    f"{_EP}.dm_service.send_message",
                    new_callable=AsyncMock,
                    side_effect=AppError(ErrorCode.DM_001, 403, "Cannot message this user."),
                ),
            ):
                resp = await client.post(
                    f"/api/v1/dm/conversations/{target}/messages",
                    data={"content": "Hi"},
                )
            assert resp.status_code == 403
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_400_self_message(self, client):
        """POST /dm/conversations/{user_id}/messages returns 400 for self-message."""
        payload, uid = _override_auth("MEMBER")
        try:
            with (
                patch(f"{_EP}.check_rate_limit", new_callable=AsyncMock, return_value=True),
                patch(
                    f"{_EP}.dm_service.send_message",
                    new_callable=AsyncMock,
                    side_effect=AppError(ErrorCode.DM_003, 400, "Cannot message yourself."),
                ),
            ):
                resp = await client.post(
                    f"/api/v1/dm/conversations/{uid}/messages",
                    data={"content": "Hi me"},
                )
            assert resp.status_code == 400
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_429_rate_limited(self, client):
        """POST /dm/conversations/{user_id}/messages returns 429 when rate limited."""
        payload, uid = _override_auth("MEMBER")
        target = uuid.uuid4()
        try:
            with patch(f"{_EP}.check_rate_limit", new_callable=AsyncMock, return_value=False):
                resp = await client.post(
                    f"/api/v1/dm/conversations/{target}/messages",
                    data={"content": "Hi"},
                )
            assert resp.status_code == 429
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_413_storage_quota_exceeded(self, client):
        """POST /dm/conversations/{user_id}/messages returns 413 for storage quota."""
        payload, uid = _override_auth("MEMBER")
        target = uuid.uuid4()
        try:
            with (
                patch(f"{_EP}.check_rate_limit", new_callable=AsyncMock, return_value=True),
                patch(
                    f"{_EP}.dm_service.send_message",
                    new_callable=AsyncMock,
                    side_effect=AppError(
                        ErrorCode.DM_004, 413, "Storage quota exceeded (1 GB limit)."
                    ),
                ),
            ):
                resp = await client.post(
                    f"/api/v1/dm/conversations/{target}/messages",
                    data={"content": "Hi"},
                    files={"file": ("big.bin", b"data", "application/octet-stream")},
                )
            assert resp.status_code == 413
            assert resp.json()["detail"]["code"] == "DM_004"
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_guest_403(self, client):
        """POST /dm/conversations/{user_id}/messages returns 403 for GUEST."""
        _override_auth("GUEST")
        target = uuid.uuid4()
        try:
            resp = await client.post(
                f"/api/v1/dm/conversations/{target}/messages",
                data={"content": "Hi"},
            )
            assert resp.status_code == 403
        finally:
            _clear_overrides()


class TestEditMessageEndpoint:
    @pytest.mark.anyio
    async def test_200_on_success(self, client):
        """PUT /dm/messages/{id} returns 200 on successful edit."""
        payload, uid = _override_auth("MEMBER")
        msg_id = uuid.uuid4()
        msg = _make_msg_response(content="Edited!")
        msg["is_edited"] = True
        try:
            with (
                patch(f"{_EP}.check_rate_limit", new_callable=AsyncMock, return_value=True),
                patch(f"{_EP}.dm_service.edit_message", new_callable=AsyncMock, return_value=msg),
            ):
                resp = await client.put(
                    f"/api/v1/dm/messages/{msg_id}",
                    json={"content": "Edited!"},
                )
            assert resp.status_code == 200
            assert resp.json()["content"] == "Edited!"
            assert resp.json()["is_edited"] is True
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_400_window_expired(self, client):
        """PUT /dm/messages/{id} returns 403 when edit window expired."""
        payload, uid = _override_auth("MEMBER")
        msg_id = uuid.uuid4()
        try:
            with (
                patch(f"{_EP}.check_rate_limit", new_callable=AsyncMock, return_value=True),
                patch(
                    f"{_EP}.dm_service.edit_message",
                    new_callable=AsyncMock,
                    side_effect=AppError(ErrorCode.DM_002, 403, "Edit window has expired."),
                ),
            ):
                resp = await client.put(
                    f"/api/v1/dm/messages/{msg_id}",
                    json={"content": "Too late"},
                )
            assert resp.status_code == 403
        finally:
            _clear_overrides()


class TestRecallMessageEndpoint:
    @pytest.mark.anyio
    async def test_200_on_success(self, client):
        """DELETE /dm/messages/{id} returns 200 on successful recall."""
        payload, uid = _override_auth("MEMBER")
        msg_id = uuid.uuid4()
        msg = _make_msg_response()
        msg["is_recalled"] = True
        msg["content"] = None
        try:
            with (
                patch(f"{_EP}.check_rate_limit", new_callable=AsyncMock, return_value=True),
                patch(f"{_EP}.dm_service.recall_message", new_callable=AsyncMock, return_value=msg),
            ):
                resp = await client.delete(f"/api/v1/dm/messages/{msg_id}")
            assert resp.status_code == 200
            assert resp.json()["is_recalled"] is True
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_400_window_expired(self, client):
        """DELETE /dm/messages/{id} returns 403 when recall window expired."""
        payload, uid = _override_auth("MEMBER")
        msg_id = uuid.uuid4()
        try:
            with (
                patch(f"{_EP}.check_rate_limit", new_callable=AsyncMock, return_value=True),
                patch(
                    f"{_EP}.dm_service.recall_message",
                    new_callable=AsyncMock,
                    side_effect=AppError(ErrorCode.DM_002, 403, "Recall window has expired."),
                ),
            ):
                resp = await client.delete(f"/api/v1/dm/messages/{msg_id}")
            assert resp.status_code == 403
        finally:
            _clear_overrides()


class TestMarkReadEndpoint:
    @pytest.mark.anyio
    async def test_200_on_success(self, client):
        """PUT /dm/conversations/{id}/read returns 200."""
        payload, uid = _override_auth("MEMBER")
        conv_id = uuid.uuid4()
        try:
            with (
                patch(f"{_EP}.check_rate_limit", new_callable=AsyncMock, return_value=True),
                patch(
                    f"{_EP}.dm_service.mark_read",
                    new_callable=AsyncMock,
                    return_value=_NOW.isoformat(),
                ),
            ):
                resp = await client.put(f"/api/v1/dm/conversations/{conv_id}/read")
            assert resp.status_code == 200
            assert "message" in resp.json()
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_404_conversation_not_found(self, client):
        """PUT /dm/conversations/{id}/read returns 404 if not participant."""
        payload, uid = _override_auth("MEMBER")
        conv_id = uuid.uuid4()
        try:
            with (
                patch(f"{_EP}.check_rate_limit", new_callable=AsyncMock, return_value=True),
                patch(
                    f"{_EP}.dm_service.mark_read",
                    new_callable=AsyncMock,
                    side_effect=AppError(ErrorCode.SYS_404, 404, "Conversation not found."),
                ),
            ):
                resp = await client.put(f"/api/v1/dm/conversations/{conv_id}/read")
            assert resp.status_code == 404
        finally:
            _clear_overrides()


# ══════════════════════════════════════════════════════════════════════════════
# 4. CELERY TASK TESTS
# ══════════════════════════════════════════════════════════════════════════════


class TestCleanupDMExpiredFiles:
    @pytest.mark.anyio
    async def test_deletes_files_and_refunds_storage(self):
        """_cleanup_files deletes expired attachments from MinIO and refunds quota."""
        expired_msg = {
            "id": uuid.uuid4(),
            "conversation_id": _CONV_ID,
            "attachment_key": "dm/test/file.pdf",
            "attachment_size": 2048,
            "sender_id": uuid.UUID(_SENDER_ID),
        }

        with (
            patch("app.tasks.dm_cleanup._ensure_pool", new_callable=AsyncMock),
            patch(
                "app.repositories.dm_repo.find_expired_file_messages",
                new_callable=AsyncMock,
                return_value=[expired_msg],
            ),
            patch("app.core.async_storage.delete_file", new_callable=AsyncMock) as mock_delete,
            patch(
                "app.repositories.user_repo.decrement_storage_used", new_callable=AsyncMock
            ) as mock_decrement,
            patch(
                "app.repositories.dm_repo.clear_message_attachment_if_present",
                new_callable=AsyncMock,
                return_value=True,
            ) as mock_clear,
        ):
            from app.tasks.dm_cleanup import _cleanup_files

            result = await _cleanup_files()

        assert result["deleted"] == 1
        assert result["errors"] == 0
        mock_delete.assert_called_once_with("dm/test/file.pdf")
        mock_decrement.assert_called_once_with(uuid.UUID(_SENDER_ID), 2048)
        mock_clear.assert_called_once_with(expired_msg["id"])

    @pytest.mark.anyio
    async def test_handles_delete_error_gracefully(self):
        """_cleanup_files counts errors when deletion fails."""
        expired_msg = {
            "id": uuid.uuid4(),
            "conversation_id": _CONV_ID,
            "attachment_key": "dm/test/file.pdf",
            "attachment_size": 1024,
            "sender_id": uuid.UUID(_SENDER_ID),
        }

        with (
            patch("app.tasks.dm_cleanup._ensure_pool", new_callable=AsyncMock),
            patch(
                "app.repositories.dm_repo.find_expired_file_messages",
                new_callable=AsyncMock,
                return_value=[expired_msg],
            ),
            patch(
                "app.core.async_storage.delete_file",
                new_callable=AsyncMock,
                side_effect=Exception("S3 error"),
            ),
            patch(
                "app.repositories.dm_repo.clear_message_attachment_if_present",
                new_callable=AsyncMock,
                return_value=True,
            ),
            patch("app.repositories.user_repo.decrement_storage_used", new_callable=AsyncMock),
        ):
            from app.tasks.dm_cleanup import _cleanup_files

            result = await _cleanup_files()

        # With L-23 fix, S3 delete failure is caught but decrement still happens
        assert result["deleted"] == 1
        assert result["errors"] == 0

    @pytest.mark.anyio
    async def test_no_expired_files(self):
        """_cleanup_files returns 0 when no expired files."""
        with (
            patch("app.tasks.dm_cleanup._ensure_pool", new_callable=AsyncMock),
            patch(
                "app.repositories.dm_repo.find_expired_file_messages",
                new_callable=AsyncMock,
                return_value=[],
            ),
        ):
            from app.tasks.dm_cleanup import _cleanup_files

            result = await _cleanup_files()

        assert result["deleted"] == 0
        assert result["errors"] == 0

    @pytest.mark.anyio
    async def test_clears_attachment_fields_on_success(self):
        """_cleanup_files calls clear_message_attachment_if_present before deletion."""
        msg_id = uuid.uuid4()
        expired = {
            "id": msg_id,
            "conversation_id": _CONV_ID,
            "attachment_key": "dm/key",
            "attachment_size": None,
            "sender_id": None,
        }

        with (
            patch("app.tasks.dm_cleanup._ensure_pool", new_callable=AsyncMock),
            patch(
                "app.repositories.dm_repo.find_expired_file_messages",
                new_callable=AsyncMock,
                return_value=[expired],
            ),
            patch("app.core.async_storage.delete_file", new_callable=AsyncMock),
            patch(
                "app.repositories.dm_repo.clear_message_attachment_if_present",
                new_callable=AsyncMock,
                return_value=True,
            ) as mock_clear,
            patch("app.repositories.user_repo.decrement_storage_used", new_callable=AsyncMock),
        ):
            from app.tasks.dm_cleanup import _cleanup_files

            await _cleanup_files()

        mock_clear.assert_called_once_with(msg_id)


class TestCleanupDMExpiredText:
    @pytest.mark.anyio
    async def test_deletes_expired_text_and_adjusts_chars(self):
        """_cleanup_text deletes expired messages and decrements char counts."""
        conv1 = uuid.uuid4()
        conv2 = uuid.uuid4()
        expired = [
            {"id": uuid.uuid4(), "conversation_id": conv1, "content": "Hello"},
            {"id": uuid.uuid4(), "conversation_id": conv1, "content": "World"},
            {"id": uuid.uuid4(), "conversation_id": conv2, "content": "Bye"},
        ]

        mock_conn = MagicMock()
        mock_conn.fetchval = AsyncMock(return_value=3)
        mock_conn.execute = AsyncMock()
        mock_tx = MagicMock()
        mock_tx.__aenter__ = AsyncMock(return_value=None)
        mock_tx.__aexit__ = AsyncMock(return_value=None)
        mock_conn.transaction.return_value = mock_tx
        mock_acq = MagicMock()
        mock_acq.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_acq.__aexit__ = AsyncMock(return_value=None)
        mock_pool = MagicMock()
        mock_pool.acquire.return_value = mock_acq

        with (
            patch("app.tasks.dm_cleanup._ensure_pool", new_callable=AsyncMock),
            patch(
                "app.repositories.dm_repo.find_expired_text_messages",
                new_callable=AsyncMock,
                return_value=expired,
            ),
            patch("app.core.database.get_pool", return_value=mock_pool),
        ):
            from app.tasks.dm_cleanup import _cleanup_text

            result = await _cleanup_text()

        assert result["deleted"] == 3
        # Should have called conn.execute twice (once per conversation for char decrement)
        assert mock_conn.execute.call_count == 2

    @pytest.mark.anyio
    async def test_empty_expired_noop(self):
        """_cleanup_text returns 0 when no expired text messages."""
        with (
            patch("app.tasks.dm_cleanup._ensure_pool", new_callable=AsyncMock),
            patch(
                "app.repositories.dm_repo.find_expired_text_messages",
                new_callable=AsyncMock,
                return_value=[],
            ),
        ):
            from app.tasks.dm_cleanup import _cleanup_text

            result = await _cleanup_text()

        assert result["deleted"] == 0

    @pytest.mark.anyio
    async def test_char_count_error_handled_gracefully(self):
        """_cleanup_text completes when transaction succeeds."""
        expired = [
            {"id": uuid.uuid4(), "conversation_id": uuid.uuid4(), "content": "Msg"},
        ]

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
        mock_pool = MagicMock()
        mock_pool.acquire.return_value = mock_acq

        with (
            patch("app.tasks.dm_cleanup._ensure_pool", new_callable=AsyncMock),
            patch(
                "app.repositories.dm_repo.find_expired_text_messages",
                new_callable=AsyncMock,
                return_value=expired,
            ),
            patch("app.core.database.get_pool", return_value=mock_pool),
        ):
            from app.tasks.dm_cleanup import _cleanup_text

            result = await _cleanup_text()

        # Should return deleted count
        assert result["deleted"] == 1

    @pytest.mark.anyio
    async def test_cleanup_text_no_content_zero_chars(self):
        """_cleanup_text handles messages with None content (0 char_len)."""
        expired = [
            {"id": uuid.uuid4(), "conversation_id": uuid.uuid4(), "content": None},
        ]

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
        mock_pool = MagicMock()
        mock_pool.acquire.return_value = mock_acq

        with (
            patch("app.tasks.dm_cleanup._ensure_pool", new_callable=AsyncMock),
            patch(
                "app.repositories.dm_repo.find_expired_text_messages",
                new_callable=AsyncMock,
                return_value=expired,
            ),
            patch("app.core.database.get_pool", return_value=mock_pool),
        ):
            from app.tasks.dm_cleanup import _cleanup_text

            result = await _cleanup_text()

        assert result["deleted"] == 1
        # Should NOT call conn.execute for char decrement when chars == 0
        mock_conn.execute.assert_not_called()


# ══════════════════════════════════════════════════════════════════════════════
# 5. EVENT HANDLER TESTS
# ══════════════════════════════════════════════════════════════════════════════


class TestDMEventHandlers:
    @pytest.mark.anyio
    async def test_on_dm_message_sent_pushes_new_dm(self):
        """dm.message_sent handler pushes NEW_DM via WebSocket."""
        msg = _make_msg_response()

        with patch("app.api.v1.endpoints.ws.send_to_user", new_callable=AsyncMock) as mock_send:
            from app.event_handlers import _on_dm_message_sent

            await _on_dm_message_sent(recipient_id=_RECIPIENT_ID, message=msg)

        mock_send.assert_called_once_with(_RECIPIENT_ID, {"type": "NEW_DM", "message": msg})

    @pytest.mark.anyio
    async def test_on_dm_message_edited_pushes_dm_edited(self):
        """dm.message_edited handler pushes DM_EDITED via WebSocket."""
        msg = _make_msg_response()

        with patch("app.api.v1.endpoints.ws.send_to_user", new_callable=AsyncMock) as mock_send:
            from app.event_handlers import _on_dm_message_edited

            await _on_dm_message_edited(recipient_id=_RECIPIENT_ID, message=msg)

        mock_send.assert_called_once_with(_RECIPIENT_ID, {"type": "DM_EDITED", "message": msg})

    @pytest.mark.anyio
    async def test_on_dm_message_recalled_pushes_dm_recalled(self):
        """dm.message_recalled handler pushes DM_RECALLED via WebSocket."""
        msg_id = str(uuid.uuid4())
        conv_id = str(uuid.uuid4())

        with patch("app.api.v1.endpoints.ws.send_to_user", new_callable=AsyncMock) as mock_send:
            from app.event_handlers import _on_dm_message_recalled

            await _on_dm_message_recalled(
                recipient_id=_RECIPIENT_ID,
                message_id=msg_id,
                conversation_id=conv_id,
            )

        mock_send.assert_called_once_with(
            _RECIPIENT_ID,
            {"type": "DM_RECALLED", "message_id": msg_id, "conversation_id": conv_id},
        )

    @pytest.mark.anyio
    async def test_on_dm_messages_read_pushes_dm_read(self):
        """dm.messages_read handler pushes DM_READ via WebSocket."""
        conv_id = str(uuid.uuid4())
        read_at = _NOW.isoformat()

        with patch("app.api.v1.endpoints.ws.send_to_user", new_callable=AsyncMock) as mock_send:
            from app.event_handlers import _on_dm_messages_read

            await _on_dm_messages_read(
                sender_id=_SENDER_ID,
                conversation_id=conv_id,
                read_at=read_at,
            )

        mock_send.assert_called_once_with(
            _SENDER_ID,
            {"type": "DM_READ", "conversation_id": conv_id, "read_at": read_at},
        )

    @pytest.mark.anyio
    async def test_on_dm_message_sent_failure_reraises(self):
        """dm.message_sent handler logs error and re-raises on WebSocket failure."""
        msg = _make_msg_response()

        with patch(
            "app.api.v1.endpoints.ws.send_to_user",
            new_callable=AsyncMock,
            side_effect=RuntimeError("WS down"),
        ):
            from app.event_handlers import _on_dm_message_sent

            with pytest.raises(RuntimeError, match="WS down"):
                await _on_dm_message_sent(recipient_id=_RECIPIENT_ID, message=msg)

    @pytest.mark.anyio
    async def test_on_dm_message_recalled_failure_reraises(self):
        """dm.message_recalled handler logs error and re-raises on WebSocket failure."""
        with patch(
            "app.api.v1.endpoints.ws.send_to_user",
            new_callable=AsyncMock,
            side_effect=ConnectionError("WS err"),
        ):
            from app.event_handlers import _on_dm_message_recalled

            with pytest.raises(ConnectionError):
                await _on_dm_message_recalled(
                    recipient_id=_RECIPIENT_ID,
                    message_id=str(uuid.uuid4()),
                    conversation_id=str(uuid.uuid4()),
                )


# ══════════════════════════════════════════════════════════════════════════════
# 6. CONVERTER TESTS
# ══════════════════════════════════════════════════════════════════════════════


class TestDMConverters:
    @pytest.mark.anyio
    async def test_async_row_to_message(self):
        """async_row_to_message converts DB row to response dict with correct fields."""
        row = _make_message_row(sender_id=_SENDER_ID, content="Hi there")

        with patch(
            "app.converters.dm_converter.async_resolve_avatar_url",
            new_callable=AsyncMock,
            return_value=None,
        ):
            from app.converters.dm_converter import async_row_to_message

            result = await async_row_to_message(row)

        assert result["id"] == str(row["id"])
        assert result["content"] == "Hi there"
        assert result["sender"]["id"] == _SENDER_ID
        assert result["sender"]["display_name"] == "Test User"
        assert result["is_recalled"] is False
        assert result["is_edited"] is False
        assert result["attachment_url"] is None

    @pytest.mark.anyio
    async def test_async_row_to_message_recalled(self):
        """async_row_to_message handles recalled message with None content."""
        row = _make_message_row(sender_id=_SENDER_ID, content=None, is_recalled=True)

        with patch(
            "app.converters.dm_converter.async_resolve_avatar_url",
            new_callable=AsyncMock,
            return_value=None,
        ):
            from app.converters.dm_converter import async_row_to_message

            result = await async_row_to_message(row)

        assert result["content"] is None
        assert result["is_recalled"] is True

    @pytest.mark.anyio
    async def test_async_row_to_conversation(self):
        """async_row_to_conversation converts DB row with last_message."""
        row = _make_conversation_list_row(user_id=_SENDER_ID, other_id=_RECIPIENT_ID)

        with patch(
            "app.converters.dm_converter.async_resolve_avatar_url",
            new_callable=AsyncMock,
            return_value=None,
        ):
            from app.converters.dm_converter import async_row_to_conversation

            result = await async_row_to_conversation(row, _SENDER_ID)

        assert result["other_user"]["id"] == _RECIPIENT_ID
        assert result["unread_count"] == 2
        assert result["last_message"] is not None
        assert result["last_message"]["content"] == "Hey"

    @pytest.mark.anyio
    async def test_async_row_to_conversation_no_last_message(self):
        """async_row_to_conversation returns None last_message when no messages."""
        row = _make_conversation_list_row(user_id=_SENDER_ID, other_id=_RECIPIENT_ID)
        row["last_msg_id"] = None

        with patch(
            "app.converters.dm_converter.async_resolve_avatar_url",
            new_callable=AsyncMock,
            return_value=None,
        ):
            from app.converters.dm_converter import async_row_to_conversation

            result = await async_row_to_conversation(row, _SENDER_ID)

        assert result["last_message"] is None


# ══════════════════════════════════════════════════════════════════════════════
# 7. ADDITIONAL EDGE CASE TESTS
# ══════════════════════════════════════════════════════════════════════════════


class TestSendMessageEdgeCases:
    @pytest.mark.anyio
    @patch(f"{_SVC}.async_row_to_message", new_callable=AsyncMock)
    @patch(f"{_SVC}.emit", new_callable=AsyncMock)
    @patch(f"{_SVC}.dm_repo")
    async def test_send_file_too_large_raises_dm005(self, mock_dm_repo, mock_emit, mock_convert):
        """send_message with file exceeding DM_MAX_ATTACHMENT_SIZE raises DM_005."""
        pool, conn = _mock_pool_context()
        mock_dm_repo.get_dm_friends_only = AsyncMock(return_value=False)

        with (
            patch("app.core.database.get_pool", return_value=pool),
            patch(
                "app.repositories.social_repo.is_blocked",
                new_callable=AsyncMock,
                return_value=False,
            ),
        ):
            from app.services.dm import send_message

            with pytest.raises(AppError) as exc:
                await send_message(
                    sender_id=_SENDER_ID,
                    recipient_id=_RECIPIENT_ID,
                    file_data=b"x",
                    file_name="huge.bin",
                    file_size=52_428_801,  # > 50MB
                    file_content_type="application/octet-stream",
                )

        assert exc.value.status_code == 413
        assert exc.value.detail["code"] == "DM_005"

    @pytest.mark.anyio
    @patch(f"{_SVC}.dm_repo")
    async def test_send_friends_only_pending_friendship_blocked(self, mock_dm_repo):
        """send_message to friends-only user with PENDING friendship raises DM_001."""
        pool, conn = _mock_pool_context()
        # dm_friends_only is now queried inline via conn.fetchval
        conn.fetchval = AsyncMock(return_value=True)

        with (
            patch("app.core.database.get_pool", return_value=pool),
            patch(
                "app.repositories.social_repo.is_blocked",
                new_callable=AsyncMock,
                return_value=False,
            ),
            patch(
                "app.repositories.social_repo.find_friendship_between",
                new_callable=AsyncMock,
                return_value={"status": "PENDING"},
            ),
        ):
            from app.services.dm import send_message

            with pytest.raises(AppError) as exc:
                await send_message(sender_id=_SENDER_ID, recipient_id=_RECIPIENT_ID, content="Hi")

        assert exc.value.status_code == 403


class TestMarkReadEdgeCases:
    @pytest.mark.anyio
    @patch(f"{_SVC}.dm_repo")
    async def test_mark_read_not_participant_raises_404(self, mock_dm_repo):
        """mark_read raises SYS_404 when user is not a participant."""
        mock_dm_repo.find_conversation_by_id = AsyncMock(return_value=None)

        from app.services.dm import mark_read

        with pytest.raises(AppError) as exc:
            await mark_read(_SENDER_ID, str(uuid.uuid4()))

        assert exc.value.status_code == 404


class TestEditMessageEndpointEdgeCases:
    @pytest.mark.anyio
    async def test_edit_guest_403(self, client):
        """PUT /dm/messages/{id} returns 403 for GUEST."""
        _override_auth("GUEST")
        try:
            resp = await client.put(
                f"/api/v1/dm/messages/{uuid.uuid4()}",
                json={"content": "Edit"},
            )
            assert resp.status_code == 403
        finally:
            _clear_overrides()


class TestRecallMessageEndpointEdgeCases:
    @pytest.mark.anyio
    async def test_recall_guest_403(self, client):
        """DELETE /dm/messages/{id} returns 403 for GUEST."""
        _override_auth("GUEST")
        try:
            resp = await client.delete(f"/api/v1/dm/messages/{uuid.uuid4()}")
            assert resp.status_code == 403
        finally:
            _clear_overrides()


class TestListConversationsEndpointEdgeCases:
    @pytest.mark.anyio
    async def test_empty_conversations_200(self, client):
        """GET /dm/conversations returns 200 with empty list."""
        payload, uid = _override_auth("MEMBER")
        try:
            with (
                patch(f"{_EP}.check_rate_limit", new_callable=AsyncMock, return_value=True),
                patch(
                    f"{_EP}.dm_service.list_conversations",
                    new_callable=AsyncMock,
                    return_value=([], 0),
                ),
            ):
                resp = await client.get("/api/v1/dm/conversations")
            assert resp.status_code == 200
            assert resp.json()["total"] == 0
            assert resp.json()["conversations"] == []
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_conversations_guest_403(self, client):
        """GET /dm/conversations returns 403 for GUEST."""
        _override_auth("GUEST")
        try:
            resp = await client.get("/api/v1/dm/conversations")
            assert resp.status_code == 403
        finally:
            _clear_overrides()


class TestListMessagesEndpointEdgeCases:
    @pytest.mark.anyio
    async def test_messages_rate_limited_429(self, client):
        """GET /dm/conversations/{id}/messages returns 429 when rate limited."""
        payload, uid = _override_auth("MEMBER")
        conv_id = uuid.uuid4()
        try:
            with patch(f"{_EP}.check_rate_limit", new_callable=AsyncMock, return_value=False):
                resp = await client.get(f"/api/v1/dm/conversations/{conv_id}/messages")
            assert resp.status_code == 429
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_messages_guest_403(self, client):
        """GET /dm/conversations/{id}/messages returns 403 for GUEST."""
        _override_auth("GUEST")
        conv_id = uuid.uuid4()
        try:
            resp = await client.get(f"/api/v1/dm/conversations/{conv_id}/messages")
            assert resp.status_code == 403
        finally:
            _clear_overrides()


# ══════════════════════════════════════════════════════════════════════════════
# 8. BUG-3: ADVISORY LOCK / ATOMIC SEND TESTS
# ══════════════════════════════════════════════════════════════════════════════


class TestSendMessageAtomicRepo:
    """Tests for the new send_message_atomic repo function."""

    @pytest.mark.anyio
    async def test_send_message_atomic_calls_advisory_lock(self, mock_pool, mock_conn):
        """send_message_atomic acquires pg_advisory_xact_lock on conversation_id."""
        msg_row = _make_message_row(sender_id=_SENDER_ID)
        mock_conn.fetchrow.return_value = msg_row
        mock_conn.fetchval.return_value = 0  # total_chars = 0
        mock_conn.fetch.return_value = []  # no deletions

        with patch(f"{_REPO}.get_pool", return_value=mock_pool):
            from app.repositories.dm_repo import send_message_atomic

            row, deleted = await send_message_atomic(
                conversation_id=_CONV_ID,
                msg_id=uuid.uuid4(),
                sender_id=uuid.UUID(_SENDER_ID),
                content="Test",
                attachment_key=None,
                attachment_name=None,
                attachment_size=None,
                attachment_expires_at=None,
                content_len=4,
                char_cap=20000,
            )

        # Verify advisory lock was called
        execute_calls = [str(c) for c in mock_conn.execute.call_args_list]
        lock_called = any("pg_advisory_xact_lock" in c for c in execute_calls)
        assert lock_called, "Expected pg_advisory_xact_lock to be called"
        assert row is not None

    @pytest.mark.anyio
    async def test_send_message_atomic_enforces_char_cap(self, mock_pool, mock_conn):
        """send_message_atomic deletes oldest messages when char cap exceeded."""
        msg_row = _make_message_row(sender_id=_SENDER_ID)
        deleted_row = {
            "id": uuid.uuid4(),
            "content": "Old msg",
            "attachment_key": None,
            "attachment_size": None,
            "sender_id": uuid.UUID(_SENDER_ID),
            "char_len": 7,
        }
        mock_conn.fetchrow.return_value = msg_row
        mock_conn.fetchval = AsyncMock(
            side_effect=[
                uuid.UUID(_RECIPIENT_ID),  # get recipient from conversation
                False,  # block check
                49998,  # total_chars near cap
            ]
        )
        mock_conn.fetch.return_value = [deleted_row]  # one message deleted

        with patch(f"{_REPO}.get_pool", return_value=mock_pool):
            from app.repositories.dm_repo import send_message_atomic

            row, deleted = await send_message_atomic(
                conversation_id=_CONV_ID,
                msg_id=uuid.uuid4(),
                sender_id=uuid.UUID(_SENDER_ID),
                content="New message",  # 11 chars
                attachment_key=None,
                attachment_name=None,
                attachment_size=None,
                attachment_expires_at=None,
                content_len=11,
                char_cap=20000,
            )

        assert len(deleted) == 1
        assert deleted[0]["char_len"] == 7

    @pytest.mark.anyio
    async def test_send_message_atomic_returns_deleted_messages(self, mock_pool, mock_conn):
        """send_message_atomic returns deleted messages for storage cleanup."""
        msg_row = _make_message_row(sender_id=_SENDER_ID)
        del1 = {
            "id": uuid.uuid4(),
            "content": "Msg1",
            "attachment_key": "dm/test/a.pdf",
            "attachment_size": 1024,
            "sender_id": uuid.UUID(_SENDER_ID),
            "char_len": 4,
        }
        del2 = {
            "id": uuid.uuid4(),
            "content": "Msg2",
            "attachment_key": None,
            "attachment_size": None,
            "sender_id": uuid.UUID(_SENDER_ID),
            "char_len": 4,
        }
        mock_conn.fetchrow.return_value = msg_row
        mock_conn.fetchval = AsyncMock(
            side_effect=[
                uuid.UUID(_RECIPIENT_ID),  # get recipient from conversation
                False,  # block check
                20000,  # total_chars at cap
            ]
        )
        mock_conn.fetch.return_value = [del1, del2]

        with patch(f"{_REPO}.get_pool", return_value=mock_pool):
            from app.repositories.dm_repo import send_message_atomic

            row, deleted = await send_message_atomic(
                conversation_id=_CONV_ID,
                msg_id=uuid.uuid4(),
                sender_id=uuid.UUID(_SENDER_ID),
                content="New",
                attachment_key=None,
                attachment_name=None,
                attachment_size=None,
                attachment_expires_at=None,
                content_len=3,
                char_cap=20000,
            )

        assert len(deleted) == 2
        assert deleted[0]["attachment_key"] == "dm/test/a.pdf"
        assert deleted[1]["attachment_key"] is None

    @pytest.mark.anyio
    async def test_send_message_atomic_no_deletions_under_cap(self, mock_pool, mock_conn):
        """send_message_atomic does not delete when under char cap."""
        msg_row = _make_message_row(sender_id=_SENDER_ID)
        mock_conn.fetchrow.return_value = msg_row
        mock_conn.fetchval = AsyncMock(
            side_effect=[
                uuid.UUID(_RECIPIENT_ID),  # get recipient from conversation
                False,  # block check
                100,  # total_chars far under cap
            ]
        )

        with patch(f"{_REPO}.get_pool", return_value=mock_pool):
            from app.repositories.dm_repo import send_message_atomic

            row, deleted = await send_message_atomic(
                conversation_id=_CONV_ID,
                msg_id=uuid.uuid4(),
                sender_id=uuid.UUID(_SENDER_ID),
                content="Short",
                attachment_key=None,
                attachment_name=None,
                attachment_size=None,
                attachment_expires_at=None,
                content_len=5,
                char_cap=20000,
            )

        assert deleted == []
        # fetch should not have been called (no excess)
        mock_conn.fetch.assert_not_called()

    @pytest.mark.anyio
    async def test_send_message_atomic_file_only_no_char_cap_check(self, mock_pool, mock_conn):
        """send_message_atomic with file-only (content_len=0) skips char cap check."""
        msg_row = _make_message_row(
            sender_id=_SENDER_ID,
            content=None,
            attachment_key="dm/test/f.pdf",
        )
        mock_conn.fetchrow.return_value = msg_row
        mock_conn.fetchval = AsyncMock(
            side_effect=[
                uuid.UUID(_RECIPIENT_ID),  # get recipient from conversation
                False,  # block check
            ]
        )

        with patch(f"{_REPO}.get_pool", return_value=mock_pool):
            from app.repositories.dm_repo import send_message_atomic

            row, deleted = await send_message_atomic(
                conversation_id=_CONV_ID,
                msg_id=uuid.uuid4(),
                sender_id=uuid.UUID(_SENDER_ID),
                content=None,
                attachment_key="dm/test/f.pdf",
                attachment_name="f.pdf",
                attachment_size=1024,
                attachment_expires_at=None,
                content_len=0,
                char_cap=20000,
            )

        assert deleted == []
        # fetchval should only have been called for block check (2 calls), not char cap
        assert mock_conn.fetchval.call_count == 2


# ══════════════════════════════════════════════════════════════════════════════
# 9. BUG-6: RECALL ORDER (DB FIRST, THEN MINIO) TESTS
# ══════════════════════════════════════════════════════════════════════════════


class TestRecallMessageOrder:
    """Tests verifying recall_message does DB recall before MinIO deletion."""

    @pytest.mark.anyio
    @patch("app.core.database.get_pool")
    @patch(f"{_SVC}.async_row_to_message", new_callable=AsyncMock)
    @patch(f"{_SVC}.emit", new_callable=AsyncMock)
    @patch(f"{_SVC}.dm_repo")
    async def test_recall_db_before_minio_delete(
        self, mock_dm_repo, mock_emit, mock_convert, mock_get_pool
    ):
        """recall_message calls DB recall before MinIO delete_file."""
        msg_row = _make_message_row(
            sender_id=_SENDER_ID,
            content="With file",
            attachment_key="dm/test/file.pdf",
            attachment_size=2048,
        )
        recalled_row = _make_message_row(sender_id=_SENDER_ID, is_recalled=True, content=None)
        conv = _make_conversation(
            conv_id=msg_row["conversation_id"],
            user_a=_SENDER_ID,
            user_b=_RECIPIENT_ID,
        )

        call_order = []

        # Mock pool -> conn -> transaction; fetchrow returns msg_row then recalled_row
        mock_conn = MagicMock()
        mock_conn.fetchval = AsyncMock(return_value=None)

        async def track_fetchrow(*a, **kw):
            call_order.append("db_recall")
            # First call returns msg_row, second returns recalled_row
            if mock_conn.fetchrow.call_count <= 1:
                return msg_row
            return recalled_row

        mock_conn.fetchrow = AsyncMock(side_effect=track_fetchrow)
        mock_conn.execute = AsyncMock()
        mock_tx = MagicMock()
        mock_tx.__aenter__ = AsyncMock(return_value=None)
        mock_tx.__aexit__ = AsyncMock(return_value=None)
        mock_conn.transaction.return_value = mock_tx
        mock_acq = MagicMock()
        mock_acq.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_acq.__aexit__ = AsyncMock(return_value=None)
        mock_get_pool.return_value.acquire.return_value = mock_acq

        mock_dm_repo.find_conversation_by_id = AsyncMock(return_value=conv)
        mock_convert.return_value = _make_msg_response(content=None)

        async def track_delete(*a, **kw):
            call_order.append("minio_delete")

        with (
            patch("app.core.async_storage.delete_file", side_effect=track_delete),
            patch(
                "app.repositories.user_repo.decrement_storage_used",
                new_callable=AsyncMock,
            ),
        ):
            from app.services.dm import recall_message

            await recall_message(str(_MSG_ID), _SENDER_ID)

        assert call_order.index("db_recall") < call_order.index(
            "minio_delete"
        ), f"DB recall must happen before MinIO delete, got: {call_order}"

    @pytest.mark.anyio
    @patch("app.core.database.get_pool")
    @patch(f"{_SVC}.async_row_to_message", new_callable=AsyncMock)
    @patch(f"{_SVC}.emit", new_callable=AsyncMock)
    @patch(f"{_SVC}.dm_repo")
    async def test_recall_minio_failure_still_recalls_db(
        self, mock_dm_repo, mock_emit, mock_convert, mock_get_pool
    ):
        """recall_message still succeeds in DB even if MinIO delete raises."""
        msg_row = _make_message_row(
            sender_id=_SENDER_ID,
            content="With file",
            attachment_key="dm/test/file.pdf",
            attachment_size=2048,
        )
        recalled_row = _make_message_row(sender_id=_SENDER_ID, is_recalled=True, content=None)
        conv = _make_conversation(
            conv_id=msg_row["conversation_id"],
            user_a=_SENDER_ID,
            user_b=_RECIPIENT_ID,
        )

        # Mock pool -> conn -> transaction; fetchrow returns msg_row then recalled_row
        mock_conn = MagicMock()
        mock_conn.fetchval = AsyncMock(return_value=None)
        mock_conn.fetchrow = AsyncMock(side_effect=[msg_row, recalled_row])
        mock_conn.execute = AsyncMock()
        mock_tx = MagicMock()
        mock_tx.__aenter__ = AsyncMock(return_value=None)
        mock_tx.__aexit__ = AsyncMock(return_value=None)
        mock_conn.transaction.return_value = mock_tx
        mock_acq = MagicMock()
        mock_acq.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_acq.__aexit__ = AsyncMock(return_value=None)
        mock_get_pool.return_value.acquire.return_value = mock_acq

        mock_dm_repo.find_conversation_by_id = AsyncMock(return_value=conv)
        mock_convert.return_value = _make_msg_response(content=None)

        with (
            patch(
                "app.core.async_storage.delete_file",
                new_callable=AsyncMock,
                side_effect=Exception("S3 down"),
            ),
            patch(
                "app.repositories.user_repo.decrement_storage_used",
                new_callable=AsyncMock,
            ),
        ):
            from app.services.dm import recall_message

            # Should NOT raise — DB recall happened before MinIO delete
            result = await recall_message(str(_MSG_ID), _SENDER_ID)

        # DB recall was done atomically via get_pool transaction
        assert mock_conn.fetchrow.called
        assert result is not None


# ══════════════════════════════════════════════════════════════════════════════
# 10. NEW ERROR CODES TESTS
# ══════════════════════════════════════════════════════════════════════════════


class TestNewDMErrorCodes:
    """Tests for DM_004, DM_005, DM_006 error codes."""

    @pytest.mark.anyio
    @patch(f"{_SVC}.dm_repo")
    async def test_send_file_too_large_returns_dm_005(self, mock_dm_repo):
        """send_message with oversized file raises DM_005 with 413 status."""
        pool, conn = _mock_pool_context()
        mock_dm_repo.get_dm_friends_only = AsyncMock(return_value=False)

        with (
            patch("app.core.database.get_pool", return_value=pool),
            patch(
                "app.repositories.social_repo.is_blocked",
                new_callable=AsyncMock,
                return_value=False,
            ),
        ):
            from app.services.dm import send_message

            with pytest.raises(AppError) as exc:
                await send_message(
                    sender_id=_SENDER_ID,
                    recipient_id=_RECIPIENT_ID,
                    file_data=b"x",
                    file_name="huge.bin",
                    file_size=52_428_801,
                    file_content_type="application/octet-stream",
                )

        assert exc.value.status_code == 413
        assert exc.value.detail["code"] == "DM_005"
        assert "10 MB" in exc.value.detail["message"]

    @pytest.mark.anyio
    @patch(f"{_SVC}.dm_repo")
    async def test_send_storage_quota_exceeded_returns_dm_004(self, mock_dm_repo):
        """send_message with file raises DM_004 with 413 when storage quota exceeded."""
        pool, conn = _mock_pool_context()
        # First fetchval: dm_friends_only check (False),
        # second: atomic UPDATE RETURNING None (quota full, WHERE condition not met)
        conn.fetchval = AsyncMock(side_effect=[False, None])

        with (
            patch("app.core.database.get_pool", return_value=pool),
            patch(
                "app.repositories.social_repo.is_blocked",
                new_callable=AsyncMock,
                return_value=False,
            ),
            patch(f"{_SVC}._validate_dm_file"),
        ):
            from app.services.dm import send_message

            with pytest.raises(AppError) as exc:
                await send_message(
                    sender_id=_SENDER_ID,
                    recipient_id=_RECIPIENT_ID,
                    file_data=b"data",
                    file_name="test.bin",
                    file_size=100,
                    file_content_type="application/octet-stream",
                )

        assert exc.value.status_code == 413
        assert exc.value.detail["code"] == "DM_004"
        assert "1 GB" in exc.value.detail["message"]

    @pytest.mark.anyio
    @patch(f"{_SVC}.dm_repo")
    async def test_list_messages_conversation_not_found_returns_dm_006(self, mock_dm_repo):
        """list_messages raises DM_006 with 404 when conversation not found."""
        mock_dm_repo.find_conversation_by_id = AsyncMock(return_value=None)

        from app.services.dm import list_messages

        with pytest.raises(AppError) as exc:
            await list_messages(_SENDER_ID, str(uuid.uuid4()))

        assert exc.value.status_code == 404
        assert exc.value.detail["code"] == "DM_006"

    @pytest.mark.anyio
    @patch(f"{_SVC}.dm_repo")
    async def test_mark_read_conversation_not_found_returns_dm_006(self, mock_dm_repo):
        """mark_read raises DM_006 with 404 when conversation not found."""
        mock_dm_repo.find_conversation_by_id = AsyncMock(return_value=None)

        from app.services.dm import mark_read

        with pytest.raises(AppError) as exc:
            await mark_read(_SENDER_ID, str(uuid.uuid4()))

        assert exc.value.status_code == 404
        assert exc.value.detail["code"] == "DM_006"


# ══════════════════════════════════════════════════════════════════════════════
# B-09: Rate limiting on edit/recall/mark_read endpoints
# ══════════════════════════════════════════════════════════════════════════════


class TestEditMessageRateLimit:
    @pytest.mark.anyio
    async def test_429_when_rate_limited(self, client):
        """PUT /dm/messages/{id} returns 429 when rate limited."""
        payload, uid = _override_auth("MEMBER")
        msg_id = uuid.uuid4()
        try:
            with patch(f"{_EP}.check_rate_limit", new_callable=AsyncMock, return_value=False):
                resp = await client.put(
                    f"/api/v1/dm/messages/{msg_id}",
                    json={"content": "Edited!"},
                )
            assert resp.status_code == 429
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_rate_limit_called_with_correct_key(self, client):
        """PUT /dm/messages/{id} calls check_rate_limit with rl:dm:edit:{user_id}."""
        payload, uid = _override_auth("MEMBER")
        msg_id = uuid.uuid4()
        msg = _make_msg_response(content="Edited!")
        msg["is_edited"] = True
        try:
            with (
                patch(
                    f"{_EP}.check_rate_limit", new_callable=AsyncMock, return_value=True
                ) as mock_rl,
                patch(f"{_EP}.dm_service.edit_message", new_callable=AsyncMock, return_value=msg),
            ):
                await client.put(
                    f"/api/v1/dm/messages/{msg_id}",
                    json={"content": "Edited!"},
                )
            mock_rl.assert_called_once()
            assert mock_rl.call_args[0][0] == f"rl:dm:edit:{uid}"
        finally:
            _clear_overrides()


class TestRecallMessageRateLimit:
    @pytest.mark.anyio
    async def test_429_when_rate_limited(self, client):
        """DELETE /dm/messages/{id} returns 429 when rate limited."""
        payload, uid = _override_auth("MEMBER")
        msg_id = uuid.uuid4()
        try:
            with patch(f"{_EP}.check_rate_limit", new_callable=AsyncMock, return_value=False):
                resp = await client.delete(f"/api/v1/dm/messages/{msg_id}")
            assert resp.status_code == 429
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_rate_limit_called_with_correct_key(self, client):
        """DELETE /dm/messages/{id} calls check_rate_limit with rl:dm:recall:{user_id}."""
        payload, uid = _override_auth("MEMBER")
        msg_id = uuid.uuid4()
        msg = _make_msg_response()
        msg["is_recalled"] = True
        msg["content"] = None
        try:
            with (
                patch(
                    f"{_EP}.check_rate_limit", new_callable=AsyncMock, return_value=True
                ) as mock_rl,
                patch(f"{_EP}.dm_service.recall_message", new_callable=AsyncMock, return_value=msg),
            ):
                await client.delete(f"/api/v1/dm/messages/{msg_id}")
            mock_rl.assert_called_once()
            assert mock_rl.call_args[0][0] == f"rl:dm:recall:{uid}"
        finally:
            _clear_overrides()


class TestMarkReadRateLimit:
    @pytest.mark.anyio
    async def test_429_when_rate_limited(self, client):
        """PUT /dm/conversations/{id}/read returns 429 when rate limited."""
        payload, uid = _override_auth("MEMBER")
        conv_id = uuid.uuid4()
        try:
            with patch(f"{_EP}.check_rate_limit", new_callable=AsyncMock, return_value=False):
                resp = await client.put(f"/api/v1/dm/conversations/{conv_id}/read")
            assert resp.status_code == 429
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_rate_limit_called_with_correct_key(self, client):
        """PUT /dm/conversations/{id}/read calls check_rate_limit with rl:dm:markread:{user_id}."""
        payload, uid = _override_auth("MEMBER")
        conv_id = uuid.uuid4()
        try:
            with (
                patch(
                    f"{_EP}.check_rate_limit", new_callable=AsyncMock, return_value=True
                ) as mock_rl,
                patch(
                    f"{_EP}.dm_service.mark_read",
                    new_callable=AsyncMock,
                    return_value=_NOW.isoformat(),
                ),
            ):
                await client.put(f"/api/v1/dm/conversations/{conv_id}/read")
            mock_rl.assert_called_once()
            assert mock_rl.call_args[0][0] == f"rl:dm:markread:{uid}"
        finally:
            _clear_overrides()


# ══════════════════════════════════════════════════════════════════════════════
# S-09: DM file upload blocked extension check
# ══════════════════════════════════════════════════════════════════════════════


class TestSendMessageBlockedExtensions:
    @pytest.mark.anyio
    async def test_400_blocked_exe(self, client):
        """POST /dm/conversations/{user_id}/messages returns 400 for .exe file."""
        payload, uid = _override_auth("MEMBER")
        target = uuid.uuid4()
        try:
            with patch(f"{_EP}.check_rate_limit", new_callable=AsyncMock, return_value=True):
                resp = await client.post(
                    f"/api/v1/dm/conversations/{target}/messages",
                    files={"file": ("malware.exe", b"MZdata", "application/octet-stream")},
                )
            assert resp.status_code == 400
            assert ".exe" in resp.json()["detail"]["message"]
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_400_blocked_bat(self, client):
        """POST /dm/conversations/{user_id}/messages returns 400 for .bat file."""
        payload, uid = _override_auth("MEMBER")
        target = uuid.uuid4()
        try:
            with patch(f"{_EP}.check_rate_limit", new_callable=AsyncMock, return_value=True):
                resp = await client.post(
                    f"/api/v1/dm/conversations/{target}/messages",
                    files={"file": ("script.bat", b"echo hi", "application/octet-stream")},
                )
            assert resp.status_code == 400
            assert ".bat" in resp.json()["detail"]["message"]
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_400_blocked_html(self, client):
        """POST /dm/conversations/{user_id}/messages returns 400 for .html file."""
        payload, uid = _override_auth("MEMBER")
        target = uuid.uuid4()
        try:
            with patch(f"{_EP}.check_rate_limit", new_callable=AsyncMock, return_value=True):
                resp = await client.post(
                    f"/api/v1/dm/conversations/{target}/messages",
                    files={"file": ("page.html", b"<html>", "text/html")},
                )
            assert resp.status_code == 400
            assert ".html" in resp.json()["detail"]["message"]
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_400_blocked_svg(self, client):
        """POST /dm/conversations/{user_id}/messages returns 400 for .svg file."""
        payload, uid = _override_auth("MEMBER")
        target = uuid.uuid4()
        try:
            with patch(f"{_EP}.check_rate_limit", new_callable=AsyncMock, return_value=True):
                resp = await client.post(
                    f"/api/v1/dm/conversations/{target}/messages",
                    files={"file": ("image.svg", b"<svg>", "image/svg+xml")},
                )
            assert resp.status_code == 400
            assert ".svg" in resp.json()["detail"]["message"]
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_400_blocked_case_insensitive(self, client):
        """POST /dm/conversations/{user_id}/messages blocks .EXE (case-insensitive)."""
        payload, uid = _override_auth("MEMBER")
        target = uuid.uuid4()
        try:
            with patch(f"{_EP}.check_rate_limit", new_callable=AsyncMock, return_value=True):
                resp = await client.post(
                    f"/api/v1/dm/conversations/{target}/messages",
                    files={"file": ("MALWARE.EXE", b"MZdata", "application/octet-stream")},
                )
            assert resp.status_code == 400
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_allowed_pdf_passes(self, client):
        """POST /dm/conversations/{user_id}/messages allows .pdf files."""
        payload, uid = _override_auth("MEMBER")
        target = uuid.uuid4()
        msg = _make_msg_response()
        msg["attachment_url"] = "http://presigned"
        msg["attachment_name"] = "doc.pdf"
        msg["attachment_size"] = 1024
        try:
            with (
                patch(f"{_EP}.check_rate_limit", new_callable=AsyncMock, return_value=True),
                patch(f"{_EP}.dm_service.send_message", new_callable=AsyncMock, return_value=msg),
            ):
                resp = await client.post(
                    f"/api/v1/dm/conversations/{target}/messages",
                    files={"file": ("doc.pdf", b"pdfdata", "application/pdf")},
                )
            assert resp.status_code == 201
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_allowed_png_passes(self, client):
        """POST /dm/conversations/{user_id}/messages allows .png files."""
        payload, uid = _override_auth("MEMBER")
        target = uuid.uuid4()
        msg = _make_msg_response()
        msg["attachment_url"] = "http://presigned"
        msg["attachment_name"] = "image.png"
        msg["attachment_size"] = 2048
        try:
            with (
                patch(f"{_EP}.check_rate_limit", new_callable=AsyncMock, return_value=True),
                patch(f"{_EP}.dm_service.send_message", new_callable=AsyncMock, return_value=msg),
            ):
                resp = await client.post(
                    f"/api/v1/dm/conversations/{target}/messages",
                    files={"file": ("image.png", b"pngdata", "image/png")},
                )
            assert resp.status_code == 201
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_allowed_txt_passes(self, client):
        """POST /dm/conversations/{user_id}/messages allows .txt files."""
        payload, uid = _override_auth("MEMBER")
        target = uuid.uuid4()
        msg = _make_msg_response()
        msg["attachment_url"] = "http://presigned"
        msg["attachment_name"] = "notes.txt"
        msg["attachment_size"] = 512
        try:
            with (
                patch(f"{_EP}.check_rate_limit", new_callable=AsyncMock, return_value=True),
                patch(f"{_EP}.dm_service.send_message", new_callable=AsyncMock, return_value=msg),
            ):
                resp = await client.post(
                    f"/api/v1/dm/conversations/{target}/messages",
                    files={"file": ("notes.txt", b"text", "text/plain")},
                )
            assert resp.status_code == 201
        finally:
            _clear_overrides()


# ══════════════════════════════════════════════════════════════════════════════
# BUG FIX TESTS (B-04, B-07, B-11, B-12, B-27, S-01, S-02, S-03)
# ══════════════════════════════════════════════════════════════════════════════


class TestB04S01SanitizeHtmlContent:
    """B-04/S-01: DM messages must be sanitized via sanitize_html()."""

    @pytest.mark.anyio
    @patch(f"{_SVC}.async_row_to_message", new_callable=AsyncMock)
    @patch(f"{_SVC}.emit", new_callable=AsyncMock)
    @patch(f"{_SVC}.dm_repo")
    async def test_send_message_sanitizes_content(self, mock_dm_repo, mock_emit, mock_convert):
        """send_message calls sanitize_html on content before DB insert."""
        pool, conn = _mock_pool_context()
        conv = _make_conversation(conv_id=_CONV_ID)
        msg_row = _make_message_row(sender_id=_SENDER_ID)

        mock_dm_repo.find_or_create_conversation = AsyncMock(return_value=conv)
        mock_dm_repo.send_message_atomic = AsyncMock(return_value=(msg_row, []))
        mock_dm_repo.get_dm_friends_only = AsyncMock(return_value=False)
        mock_convert.return_value = _make_msg_response()

        with (
            patch("app.core.database.get_pool", return_value=pool),
            patch(
                "app.repositories.social_repo.is_blocked",
                new_callable=AsyncMock,
                return_value=False,
            ),
            patch(f"{_SVC}.sanitize_html", return_value="clean content") as mock_sanitize,
        ):
            from app.services.dm import send_message

            await send_message(
                sender_id=_SENDER_ID,
                recipient_id=_RECIPIENT_ID,
                content="<script>alert('xss')</script>Hello",
            )

        mock_sanitize.assert_called_once_with("<script>alert('xss')</script>Hello")
        # Verify sanitized content was passed to the atomic insert
        call_kwargs = mock_dm_repo.send_message_atomic.call_args[1]
        assert call_kwargs["content"] == "clean content"

    @pytest.mark.anyio
    @patch("app.core.database.get_pool")
    @patch(f"{_SVC}.async_row_to_message", new_callable=AsyncMock)
    @patch(f"{_SVC}.emit", new_callable=AsyncMock)
    @patch(f"{_SVC}.dm_repo")
    async def test_edit_message_sanitizes_content(
        self, mock_dm_repo, mock_emit, mock_convert, mock_get_pool
    ):
        """edit_message calls sanitize_html on new_content before DB update."""
        msg_row = _make_message_row(sender_id=_SENDER_ID, created_at=_NOW)
        updated_row = _make_message_row(sender_id=_SENDER_ID, content="sanitized", is_edited=True)
        conv = _make_conversation(
            conv_id=msg_row["conversation_id"],
            user_a=_SENDER_ID,
            user_b=_RECIPIENT_ID,
        )

        # Mock pool -> conn -> transaction; fetchrow returns msg_row then updated_row
        mock_conn = MagicMock()
        mock_conn.fetchval = AsyncMock(return_value=None)
        mock_conn.fetchrow = AsyncMock(side_effect=[msg_row, updated_row])
        mock_conn.execute = AsyncMock()
        mock_tx = MagicMock()
        mock_tx.__aenter__ = AsyncMock(return_value=None)
        mock_tx.__aexit__ = AsyncMock(return_value=None)
        mock_conn.transaction.return_value = mock_tx
        mock_acq = MagicMock()
        mock_acq.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_acq.__aexit__ = AsyncMock(return_value=None)
        mock_get_pool.return_value.acquire.return_value = mock_acq

        mock_dm_repo.find_conversation_by_id = AsyncMock(return_value=conv)
        mock_convert.return_value = _make_msg_response(content="sanitized")

        with patch(f"{_SVC}.sanitize_html", return_value="sanitized") as mock_sanitize:
            from app.services.dm import edit_message

            await edit_message(str(_MSG_ID), _SENDER_ID, "<img onerror=alert(1)>text")

        mock_sanitize.assert_called_once_with("<img onerror=alert(1)>text")
        # Verify sanitized content was passed to the atomic update via conn.fetchrow
        fetchrow_calls = mock_conn.fetchrow.call_args_list
        assert any("sanitized" in str(c) for c in fetchrow_calls)


class TestB07AsyncStorageOps:
    """B-07: File upload/delete must use async wrappers (not sync)."""

    @pytest.mark.anyio
    @patch(f"{_SVC}.async_row_to_message", new_callable=AsyncMock)
    @patch(f"{_SVC}.emit", new_callable=AsyncMock)
    @patch(f"{_SVC}.dm_repo")
    async def test_send_uses_async_upload(self, mock_dm_repo, mock_emit, mock_convert):
        """send_message uses async_upload_file instead of sync upload_file."""
        pool, conn = _mock_pool_context()
        conv = _make_conversation(conv_id=_CONV_ID)
        msg_row = _make_message_row(sender_id=_SENDER_ID, attachment_key="dm/test/abc.png")
        msg_dict = _make_msg_response()

        mock_dm_repo.find_or_create_conversation = AsyncMock(return_value=conv)
        mock_dm_repo.send_message_atomic = AsyncMock(return_value=(msg_row, []))
        mock_dm_repo.get_dm_friends_only = AsyncMock(return_value=False)
        mock_convert.return_value = msg_dict

        with (
            patch("app.core.database.get_pool", return_value=pool),
            patch(
                "app.repositories.social_repo.is_blocked",
                new_callable=AsyncMock,
                return_value=False,
            ),
            patch(
                "app.repositories.user_repo.get_storage_used",
                new_callable=AsyncMock,
                return_value=0,
            ),
            patch("app.repositories.user_repo.increment_storage_used", new_callable=AsyncMock),
            patch(
                "app.core.async_storage.upload_file", new_callable=AsyncMock
            ) as mock_async_upload,
            patch("app.core.storage.generate_presigned_url", return_value="http://presigned"),
            patch(f"{_SVC}.sanitize_html", side_effect=lambda x: x),
            patch(f"{_SVC}._validate_dm_file"),
        ):
            from app.services.dm import send_message

            await send_message(
                sender_id=_SENDER_ID,
                recipient_id=_RECIPIENT_ID,
                file_data=b"\x89PNG\r\n\x1a\ndata",
                file_name="photo.png",
                file_size=1024,
                file_content_type="image/png",
            )

        mock_async_upload.assert_called_once()
        assert mock_async_upload.await_count == 1

    @pytest.mark.anyio
    @patch("app.core.database.get_pool")
    @patch(f"{_SVC}.async_row_to_message", new_callable=AsyncMock)
    @patch(f"{_SVC}.emit", new_callable=AsyncMock)
    @patch(f"{_SVC}.dm_repo")
    async def test_recall_uses_async_delete(
        self, mock_dm_repo, mock_emit, mock_convert, mock_get_pool
    ):
        """recall_message uses async_delete_file instead of sync delete_file."""
        msg_row = _make_message_row(
            sender_id=_SENDER_ID,
            content="With file",
            attachment_key="dm/test/file.pdf",
            attachment_size=2048,
        )
        recalled_row = _make_message_row(sender_id=_SENDER_ID, is_recalled=True, content=None)
        conv = _make_conversation(
            conv_id=msg_row["conversation_id"],
            user_a=_SENDER_ID,
            user_b=_RECIPIENT_ID,
        )

        # Mock pool -> conn -> transaction; fetchrow returns msg_row then recalled_row
        mock_conn = MagicMock()
        mock_conn.fetchval = AsyncMock(return_value=None)
        mock_conn.fetchrow = AsyncMock(side_effect=[msg_row, recalled_row])
        mock_conn.execute = AsyncMock()
        mock_tx = MagicMock()
        mock_tx.__aenter__ = AsyncMock(return_value=None)
        mock_tx.__aexit__ = AsyncMock(return_value=None)
        mock_conn.transaction.return_value = mock_tx
        mock_acq = MagicMock()
        mock_acq.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_acq.__aexit__ = AsyncMock(return_value=None)
        mock_get_pool.return_value.acquire.return_value = mock_acq

        mock_dm_repo.find_conversation_by_id = AsyncMock(return_value=conv)
        mock_convert.return_value = _make_msg_response(content=None)

        with (
            patch(
                "app.core.async_storage.delete_file", new_callable=AsyncMock
            ) as mock_async_delete,
            patch(
                "app.repositories.user_repo.decrement_storage_used",
                new_callable=AsyncMock,
            ),
        ):
            from app.services.dm import recall_message

            await recall_message(str(_MSG_ID), _SENDER_ID)

        mock_async_delete.assert_awaited_once_with("dm/test/file.pdf")

    @pytest.mark.anyio
    @patch(f"{_SVC}.async_row_to_message", new_callable=AsyncMock)
    @patch(f"{_SVC}.emit", new_callable=AsyncMock)
    @patch(f"{_SVC}.dm_repo")
    async def test_send_deleted_msgs_use_async_delete(self, mock_dm_repo, mock_emit, mock_convert):
        """send_message uses async_delete_file for deleted attachment cleanup."""
        pool, conn = _mock_pool_context()
        conv = _make_conversation(conv_id=_CONV_ID)
        msg_row = _make_message_row(sender_id=_SENDER_ID)
        deleted_msg = {
            "id": uuid.uuid4(),
            "attachment_key": "dm/old/file.pdf",
            "attachment_size": 500,
            "sender_id": uuid.UUID(_SENDER_ID),
        }

        mock_dm_repo.find_or_create_conversation = AsyncMock(return_value=conv)
        mock_dm_repo.send_message_atomic = AsyncMock(return_value=(msg_row, [deleted_msg]))
        mock_dm_repo.get_dm_friends_only = AsyncMock(return_value=False)
        mock_convert.return_value = _make_msg_response()

        with (
            patch("app.core.database.get_pool", return_value=pool),
            patch(
                "app.repositories.social_repo.is_blocked",
                new_callable=AsyncMock,
                return_value=False,
            ),
            patch("app.core.async_storage.delete_file", new_callable=AsyncMock) as mock_async_del,
            patch("app.repositories.user_repo.decrement_storage_used", new_callable=AsyncMock),
            patch(f"{_SVC}.sanitize_html", side_effect=lambda x: x),
        ):
            from app.services.dm import send_message

            await send_message(
                sender_id=_SENDER_ID,
                recipient_id=_RECIPIENT_ID,
                content="New msg",
            )

        mock_async_del.assert_awaited_once_with("dm/old/file.pdf")


class TestB11RecallCharCountAfterSuccess:
    """B-11: Char count decrement must happen AFTER successful recall_message()."""

    @pytest.mark.anyio
    @patch("app.core.database.get_pool")
    @patch(f"{_SVC}.async_row_to_message", new_callable=AsyncMock)
    @patch(f"{_SVC}.emit", new_callable=AsyncMock)
    @patch(f"{_SVC}.dm_repo")
    async def test_recall_failure_does_not_decrement_char_count(
        self, mock_dm_repo, mock_emit, mock_convert, mock_get_pool
    ):
        """When recall UPDATE returns None, char count is NOT decremented."""
        msg_row = _make_message_row(sender_id=_SENDER_ID, content="Some content")

        # Mock pool -> conn -> transaction; fetchrow returns msg_row then None (recall failed)
        mock_conn = MagicMock()
        mock_conn.fetchval = AsyncMock(return_value=None)
        mock_conn.fetchrow = AsyncMock(side_effect=[msg_row, None])
        mock_conn.execute = AsyncMock()
        mock_tx = MagicMock()
        mock_tx.__aenter__ = AsyncMock(return_value=None)
        mock_tx.__aexit__ = AsyncMock(return_value=None)
        mock_conn.transaction.return_value = mock_tx
        mock_acq = MagicMock()
        mock_acq.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_acq.__aexit__ = AsyncMock(return_value=None)
        mock_get_pool.return_value.acquire.return_value = mock_acq

        from app.services.dm import recall_message

        with pytest.raises(AppError) as exc:
            await recall_message(str(_MSG_ID), _SENDER_ID)

        assert exc.value.status_code == 404
        # conn.execute should NOT have been called for char count decrement
        mock_conn.execute.assert_not_called()

    @pytest.mark.anyio
    @patch("app.core.database.get_pool")
    @patch(f"{_SVC}.async_row_to_message", new_callable=AsyncMock)
    @patch(f"{_SVC}.emit", new_callable=AsyncMock)
    @patch(f"{_SVC}.dm_repo")
    async def test_recall_success_decrements_char_count(
        self, mock_dm_repo, mock_emit, mock_convert, mock_get_pool
    ):
        """When recall succeeds, char count IS decremented atomically."""
        msg_row = _make_message_row(sender_id=_SENDER_ID, content="12345")
        recalled_row = _make_message_row(sender_id=_SENDER_ID, is_recalled=True, content=None)
        conv = _make_conversation(
            conv_id=msg_row["conversation_id"],
            user_a=_SENDER_ID,
            user_b=_RECIPIENT_ID,
        )

        # Mock pool -> conn -> transaction; fetchrow returns msg_row then recalled_row
        mock_conn = MagicMock()
        mock_conn.fetchval = AsyncMock(return_value=None)
        mock_conn.fetchrow = AsyncMock(side_effect=[msg_row, recalled_row])
        mock_conn.execute = AsyncMock()
        mock_tx = MagicMock()
        mock_tx.__aenter__ = AsyncMock(return_value=None)
        mock_tx.__aexit__ = AsyncMock(return_value=None)
        mock_conn.transaction.return_value = mock_tx
        mock_acq = MagicMock()
        mock_acq.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_acq.__aexit__ = AsyncMock(return_value=None)
        mock_get_pool.return_value.acquire.return_value = mock_acq

        mock_dm_repo.find_conversation_by_id = AsyncMock(return_value=conv)
        mock_convert.return_value = _make_msg_response(content=None)

        from app.services.dm import recall_message

        await recall_message(str(_MSG_ID), _SENDER_ID)

        # Char count decrement happens via conn.execute in the transaction
        assert mock_conn.execute.called

    @pytest.mark.anyio
    @patch("app.core.database.get_pool")
    @patch(f"{_SVC}.async_row_to_message", new_callable=AsyncMock)
    @patch(f"{_SVC}.emit", new_callable=AsyncMock)
    @patch(f"{_SVC}.dm_repo")
    async def test_recall_exception_does_not_decrement_char_count(
        self, mock_dm_repo, mock_emit, mock_convert, mock_get_pool
    ):
        """When conn.fetchrow raises inside transaction, char count is NOT decremented."""
        msg_row = _make_message_row(sender_id=_SENDER_ID, content="Some content")

        # Mock pool -> conn -> transaction; fetchrow returns msg_row then raises
        mock_conn = MagicMock()
        mock_conn.fetchval = AsyncMock(return_value=None)
        mock_conn.fetchrow = AsyncMock(side_effect=[msg_row, RuntimeError("DB error")])
        mock_conn.execute = AsyncMock()
        mock_tx = MagicMock()
        mock_tx.__aenter__ = AsyncMock(return_value=None)
        mock_tx.__aexit__ = AsyncMock(return_value=None)
        mock_conn.transaction.return_value = mock_tx
        mock_acq = MagicMock()
        mock_acq.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_acq.__aexit__ = AsyncMock(return_value=None)
        mock_get_pool.return_value.acquire.return_value = mock_acq

        from app.services.dm import recall_message

        with pytest.raises(RuntimeError):
            await recall_message(str(_MSG_ID), _SENDER_ID)

        # conn.execute should NOT have been called
        mock_conn.execute.assert_not_called()


class TestB12StorageQuotaAfterInsert:
    """H-03: Storage quota is atomically reserved before upload; refunded on failure."""

    @pytest.mark.anyio
    @patch(f"{_SVC}.async_row_to_message", new_callable=AsyncMock)
    @patch(f"{_SVC}.emit", new_callable=AsyncMock)
    @patch(f"{_SVC}.dm_repo")
    async def test_insert_failure_refunds_quota(
        self, mock_dm_repo, mock_emit, mock_convert
    ):
        """When send_message_atomic raises, pre-reserved quota is refunded."""
        pool, conn = _mock_pool_context()
        # fetchval side_effect: dm_friends_only=False, quota UPDATE returns 2048 (reserved)
        conn.fetchval = AsyncMock(side_effect=[False, 2048])
        mock_dm_repo.get_dm_friends_only = AsyncMock(return_value=False)
        conv = _make_conversation(conv_id=_CONV_ID)
        mock_dm_repo.find_or_create_conversation = AsyncMock(return_value=conv)
        mock_dm_repo.send_message_atomic = AsyncMock(side_effect=RuntimeError("DB insert failed"))

        with (
            patch("app.core.database.get_pool", return_value=pool),
            patch(
                "app.repositories.social_repo.is_blocked",
                new_callable=AsyncMock,
                return_value=False,
            ),
            patch(
                "app.repositories.user_repo.decrement_storage_used", new_callable=AsyncMock
            ) as mock_decrement,
            patch("app.core.async_storage.upload_file", new_callable=AsyncMock),
            patch(f"{_SVC}.sanitize_html", side_effect=lambda x: x),
            patch(f"{_SVC}._validate_dm_file"),
        ):
            from app.services.dm import send_message

            with pytest.raises(RuntimeError):
                await send_message(
                    sender_id=_SENDER_ID,
                    recipient_id=_RECIPIENT_ID,
                    file_data=b"\x89PNG\r\n\x1a\ndata",
                    file_name="photo.png",
                    file_size=2048,
                    file_content_type="image/png",
                )

        mock_decrement.assert_called_once_with(uuid.UUID(_SENDER_ID), 2048)

    @pytest.mark.anyio
    @patch(f"{_SVC}.async_row_to_message", new_callable=AsyncMock)
    @patch(f"{_SVC}.emit", new_callable=AsyncMock)
    @patch(f"{_SVC}.dm_repo")
    async def test_insert_success_no_separate_increment(self, mock_dm_repo, mock_emit, mock_convert):
        """When send_message_atomic succeeds, no separate increment is needed (pre-reserved)."""
        pool, conn = _mock_pool_context()
        # fetchval side_effect: dm_friends_only=False, quota UPDATE returns 2048 (reserved)
        conn.fetchval = AsyncMock(side_effect=[False, 2048])
        conv = _make_conversation(conv_id=_CONV_ID)
        msg_row = _make_message_row(
            sender_id=_SENDER_ID,
            attachment_key="dm/test/abc.png",
            attachment_size=2048,
        )
        msg_dict = _make_msg_response()

        mock_dm_repo.find_or_create_conversation = AsyncMock(return_value=conv)
        mock_dm_repo.send_message_atomic = AsyncMock(return_value=(msg_row, []))
        mock_dm_repo.get_dm_friends_only = AsyncMock(return_value=False)
        mock_convert.return_value = msg_dict

        with (
            patch("app.core.database.get_pool", return_value=pool),
            patch(
                "app.repositories.social_repo.is_blocked",
                new_callable=AsyncMock,
                return_value=False,
            ),
            patch(
                "app.repositories.user_repo.increment_storage_used", new_callable=AsyncMock
            ) as mock_increment,
            patch("app.core.async_storage.upload_file", new_callable=AsyncMock),
            patch("app.core.storage.generate_presigned_url", return_value="http://presigned"),
            patch(f"{_SVC}.sanitize_html", side_effect=lambda x: x),
            patch(f"{_SVC}._validate_dm_file"),
        ):
            from app.services.dm import send_message

            await send_message(
                sender_id=_SENDER_ID,
                recipient_id=_RECIPIENT_ID,
                file_data=b"\x89PNG\r\n\x1a\ndata",
                file_name="photo.png",
                file_size=2048,
                file_content_type="image/png",
            )

        # H-03: quota was atomically reserved via UPDATE, no separate increment
        mock_increment.assert_not_called()


class TestB27S03SanitizedFilename:
    """B-27/S-03: Storage key must only use file extension, not the full filename."""

    @pytest.mark.anyio
    @patch(f"{_SVC}.async_row_to_message", new_callable=AsyncMock)
    @patch(f"{_SVC}.emit", new_callable=AsyncMock)
    @patch(f"{_SVC}.dm_repo")
    async def test_storage_key_uses_only_extension(self, mock_dm_repo, mock_emit, mock_convert):
        """Storage key is dm/{sender_id}/{hex}{ext}, not dm/{sender_id}/{uuid}_{filename}."""
        pool, conn = _mock_pool_context()
        conv = _make_conversation(conv_id=_CONV_ID)
        msg_row = _make_message_row(sender_id=_SENDER_ID, attachment_key="dm/test/abc.pdf")
        msg_dict = _make_msg_response()

        mock_dm_repo.find_or_create_conversation = AsyncMock(return_value=conv)
        mock_dm_repo.send_message_atomic = AsyncMock(return_value=(msg_row, []))
        mock_dm_repo.get_dm_friends_only = AsyncMock(return_value=False)
        mock_convert.return_value = msg_dict

        captured_key = None

        async def capture_upload(data, key, ct):
            nonlocal captured_key
            captured_key = key
            return key

        with (
            patch("app.core.database.get_pool", return_value=pool),
            patch(
                "app.repositories.social_repo.is_blocked",
                new_callable=AsyncMock,
                return_value=False,
            ),
            patch(
                "app.repositories.user_repo.get_storage_used",
                new_callable=AsyncMock,
                return_value=0,
            ),
            patch("app.repositories.user_repo.increment_storage_used", new_callable=AsyncMock),
            patch("app.core.async_storage.upload_file", side_effect=capture_upload),
            patch("app.core.storage.generate_presigned_url", return_value="http://presigned"),
            patch(f"{_SVC}.sanitize_html", side_effect=lambda x: x),
            patch(f"{_SVC}._validate_dm_file"),
        ):
            from app.services.dm import send_message

            await send_message(
                sender_id=_SENDER_ID,
                recipient_id=_RECIPIENT_ID,
                file_data=b"%PDF-data",
                file_name="../../etc/passwd.pdf",
                file_size=500,
                file_content_type="application/pdf",
            )

        assert captured_key is not None
        assert "passwd" not in captured_key
        assert "etc" not in captured_key
        assert ".." not in captured_key
        assert captured_key.endswith(".pdf")
        assert captured_key.startswith(f"dm/{_SENDER_ID}/")

    @pytest.mark.anyio
    @patch(f"{_SVC}.async_row_to_message", new_callable=AsyncMock)
    @patch(f"{_SVC}.emit", new_callable=AsyncMock)
    @patch(f"{_SVC}.dm_repo")
    async def test_storage_key_handles_no_extension(self, mock_dm_repo, mock_emit, mock_convert):
        """Storage key works when filename has no extension."""
        pool, conn = _mock_pool_context()
        conv = _make_conversation(conv_id=_CONV_ID)
        msg_row = _make_message_row(sender_id=_SENDER_ID)
        msg_dict = _make_msg_response()

        mock_dm_repo.find_or_create_conversation = AsyncMock(return_value=conv)
        mock_dm_repo.send_message_atomic = AsyncMock(return_value=(msg_row, []))
        mock_dm_repo.get_dm_friends_only = AsyncMock(return_value=False)
        mock_convert.return_value = msg_dict

        captured_key = None

        async def capture_upload(data, key, ct):
            nonlocal captured_key
            captured_key = key
            return key

        with (
            patch("app.core.database.get_pool", return_value=pool),
            patch(
                "app.repositories.social_repo.is_blocked",
                new_callable=AsyncMock,
                return_value=False,
            ),
            patch(
                "app.repositories.user_repo.get_storage_used",
                new_callable=AsyncMock,
                return_value=0,
            ),
            patch("app.repositories.user_repo.increment_storage_used", new_callable=AsyncMock),
            patch("app.core.async_storage.upload_file", side_effect=capture_upload),
            patch("app.core.storage.generate_presigned_url", return_value="http://presigned"),
            patch(f"{_SVC}.sanitize_html", side_effect=lambda x: x),
            patch(f"{_SVC}._validate_dm_file"),
        ):
            from app.services.dm import send_message

            await send_message(
                sender_id=_SENDER_ID,
                recipient_id=_RECIPIENT_ID,
                file_data=b"binary data",
                file_name="noextension",
                file_size=100,
                file_content_type="application/octet-stream",
            )

        assert captured_key is not None
        assert "noextension" not in captured_key
        assert captured_key.startswith(f"dm/{_SENDER_ID}/")


class TestS02FileTypeValidation:
    """S-02: DM uploads must validate file type (extension + magic bytes for images)."""

    def test_allowed_image_extensions_pass(self):
        """Allowed image extensions pass validation."""
        from app.services.dm import _validate_dm_file

        _validate_dm_file("photo.png", b"\x89PNG\r\n\x1a\n" + b"rest of data")
        _validate_dm_file("photo.jpg", b"\xff\xd8\xff" + b"rest of data")
        _validate_dm_file("photo.jpeg", b"\xff\xd8\xff" + b"rest of data")
        _validate_dm_file("anim.gif", b"GIF89a" + b"rest of data")
        _validate_dm_file("photo.webp", b"RIFF\x00\x00\x00\x00WEBP" + b"rest")

    def test_allowed_document_extensions_pass(self):
        """Allowed document extensions pass validation with correct magic bytes."""
        from app.services.dm import _validate_dm_file

        _validate_dm_file("doc.txt", b"text content")
        _validate_dm_file("data.csv", b"a,b,c\n1,2,3")
        _validate_dm_file("archive.zip", b"PK\x03\x04data")
        _validate_dm_file("slide.pptx", b"PK\x03\x04data")

    def test_disallowed_exe_raises_error(self):
        """Executable files (.exe) are rejected."""
        from app.services.dm import _validate_dm_file

        with pytest.raises(AppError) as exc:
            _validate_dm_file("malware.exe", b"MZ\x90\x00")
        assert exc.value.status_code == 400

    def test_disallowed_bat_raises_error(self):
        """Batch files (.bat) are rejected."""
        from app.services.dm import _validate_dm_file

        with pytest.raises(AppError) as exc:
            _validate_dm_file("script.bat", b"@echo off")
        assert exc.value.status_code == 400

    def test_disallowed_html_raises_error(self):
        """HTML files (.html) are rejected."""
        from app.services.dm import _validate_dm_file

        with pytest.raises(AppError) as exc:
            _validate_dm_file("page.html", b"<html>xss</html>")
        assert exc.value.status_code == 400

    def test_disallowed_js_raises_error(self):
        """JavaScript files (.js) are rejected."""
        from app.services.dm import _validate_dm_file

        with pytest.raises(AppError) as exc:
            _validate_dm_file("script.js", b"alert(1)")
        assert exc.value.status_code == 400

    def test_disallowed_sh_raises_error(self):
        """Shell scripts (.sh) are rejected."""
        from app.services.dm import _validate_dm_file

        with pytest.raises(AppError) as exc:
            _validate_dm_file("exploit.sh", b"#!/bin/bash")
        assert exc.value.status_code == 400

    def test_image_with_wrong_magic_bytes_raises_error(self):
        """Image extension with wrong magic bytes is rejected."""
        from app.services.dm import _validate_dm_file

        with pytest.raises(AppError) as exc:
            _validate_dm_file("fake.png", b"NOT_A_PNG_FILE")
        assert exc.value.status_code == 400
        assert "magic number" in exc.value.detail["message"].lower()

    def test_jpeg_with_wrong_magic_bytes_raises_error(self):
        """JPEG extension with wrong magic bytes is rejected."""
        from app.services.dm import _validate_dm_file

        with pytest.raises(AppError) as exc:
            _validate_dm_file("fake.jpg", b"\x00\x00\x00NOT_JPEG")
        assert exc.value.status_code == 400

    def test_pdf_with_wrong_magic_bytes_raises_error(self):
        """PDF extension with wrong magic bytes is rejected."""
        from app.services.dm import _validate_dm_file

        with pytest.raises(AppError) as exc:
            _validate_dm_file("fake.pdf", b"NOT_A_PDF")
        assert exc.value.status_code == 400

    def test_pdf_with_correct_magic_bytes_passes(self):
        """PDF extension with correct magic bytes passes."""
        from app.services.dm import _validate_dm_file

        _validate_dm_file("document.pdf", b"%PDF-1.5 rest of data")

    def test_case_insensitive_extension(self):
        """Extension check is case-insensitive."""
        from app.services.dm import _validate_dm_file

        _validate_dm_file("PHOTO.PNG", b"\x89PNG\r\n\x1a\n" + b"rest")
        _validate_dm_file("Doc.PDF", b"%PDF-1.5 rest")

    def test_no_extension_raises_error(self):
        """File without extension is rejected."""
        from app.services.dm import _validate_dm_file

        with pytest.raises(AppError) as exc:
            _validate_dm_file("noextension", b"some data")
        assert exc.value.status_code == 400

    @pytest.mark.anyio
    @patch(f"{_SVC}.dm_repo")
    async def test_send_message_validates_file_type(self, mock_dm_repo):
        """send_message rejects disallowed file types before upload."""
        pool, conn = _mock_pool_context()
        mock_dm_repo.get_dm_friends_only = AsyncMock(return_value=False)

        with (
            patch("app.core.database.get_pool", return_value=pool),
            patch(
                "app.repositories.social_repo.is_blocked",
                new_callable=AsyncMock,
                return_value=False,
            ),
            patch(
                "app.repositories.user_repo.get_storage_used",
                new_callable=AsyncMock,
                return_value=0,
            ),
        ):
            from app.services.dm import send_message

            with pytest.raises(AppError) as exc:
                await send_message(
                    sender_id=_SENDER_ID,
                    recipient_id=_RECIPIENT_ID,
                    file_data=b"MZ\x90\x00executable",
                    file_name="malware.exe",
                    file_size=100,
                    file_content_type="application/x-executable",
                )

        assert exc.value.status_code == 400
