"""Tests for social/friend/DM/recommendation bugfixes.

Covers:
- B1: find_pending_requests fallback COUNT on empty page
- B2: find_pending_requests filters deleted users
- B3: find_followers/find_following fallback COUNT uses correct $2 param
- B4: send_friend_request block check inside transaction
- B5: DM send_message block+friendship checks inside transaction
- B6: Recommendations exclude blocked users
"""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.errors import AppError

# ── Helpers ──────────────────────────────────────────────────────────────────

_REPO = "app.repositories.social_repo"
_REC_REPO = "app.repositories.recommendation_repo"
_DM_REPO = "app.repositories.dm_repo"
_DM_SVC = "app.services.dm"


def _make_friendship(
    requester_id=None, addressee_id=None, status="PENDING", friendship_id=None
):
    now = datetime.now(timezone.utc)
    return {
        "id": friendship_id or uuid.uuid4(),
        "requester_id": requester_id or uuid.uuid4(),
        "addressee_id": addressee_id or uuid.uuid4(),
        "status": status,
        "created_at": now,
        "updated_at": now,
    }


# ===========================================================================
# B1: find_pending_requests — empty page returns actual total (not 0)
# ===========================================================================


class TestFindPendingRequestsFallback:
    @pytest.mark.anyio
    async def test_empty_page_returns_actual_total(self, mock_conn):
        """When rows are empty (page beyond results), fallback COUNT returns real total."""
        from app.repositories.social_repo import find_pending_requests

        mock_conn.fetch = AsyncMock(return_value=[])
        mock_conn.fetchval = AsyncMock(return_value=5)

        result, total = await find_pending_requests(mock_conn, uuid.uuid4(), page=3, page_size=2)
        assert result == []
        assert total == 5
        mock_conn.fetchval.assert_awaited_once()

    @pytest.mark.anyio
    async def test_empty_page_fallback_sql_filters_deleted(self, mock_conn):
        """Fallback COUNT SQL includes is_deleted = false for both users."""
        from app.repositories.social_repo import find_pending_requests

        mock_conn.fetch = AsyncMock(return_value=[])
        mock_conn.fetchval = AsyncMock(return_value=0)

        await find_pending_requests(mock_conn, uuid.uuid4())
        sql = mock_conn.fetchval.call_args[0][0]
        assert "req.is_deleted = false" in sql
        assert "adr.is_deleted = false" in sql


# ===========================================================================
# B2: find_pending_requests — main query filters deleted users
# ===========================================================================


class TestFindPendingRequestsDeletedFilter:
    @pytest.mark.anyio
    async def test_main_query_filters_deleted_users(self, mock_conn):
        """Main pending requests query SQL includes is_deleted = false."""
        from app.repositories.social_repo import find_pending_requests

        mock_conn.fetch = AsyncMock(return_value=[])
        mock_conn.fetchval = AsyncMock(return_value=0)

        await find_pending_requests(mock_conn, uuid.uuid4())
        sql = mock_conn.fetch.call_args[0][0]
        assert "req.is_deleted = false" in sql
        assert "adr.is_deleted = false" in sql


# ===========================================================================
# B3: find_followers/find_following — fallback COUNT uses $2 for exclude
# ===========================================================================


class TestFollowersFallbackParams:
    @pytest.mark.anyio
    async def test_find_followers_fallback_with_exclude(self, mock_conn):
        """Fallback COUNT in find_followers uses $2::uuid[] (not $4)."""
        from app.repositories.social_repo import find_followers

        user_id = uuid.uuid4()
        exclude_ids = [uuid.uuid4(), uuid.uuid4()]
        mock_conn.fetch = AsyncMock(return_value=[])
        mock_conn.fetchval = AsyncMock(return_value=3)

        result, total = await find_followers(
            mock_conn, user_id, page=2, page_size=5, exclude_user_ids=exclude_ids
        )
        assert total == 3
        # Verify fallback SQL uses $2 (not $4)
        sql = mock_conn.fetchval.call_args[0][0]
        assert "$2::uuid[]" in sql
        assert "$4" not in sql

    @pytest.mark.anyio
    async def test_find_followers_fallback_without_exclude(self, mock_conn):
        """Fallback COUNT in find_followers works without exclude_user_ids."""
        from app.repositories.social_repo import find_followers

        mock_conn.fetch = AsyncMock(return_value=[])
        mock_conn.fetchval = AsyncMock(return_value=7)

        result, total = await find_followers(mock_conn, uuid.uuid4(), page=2, page_size=5)
        assert total == 7
        sql = mock_conn.fetchval.call_args[0][0]
        assert "$2" not in sql or "uuid[]" not in sql  # no exclusion clause

    @pytest.mark.anyio
    async def test_find_following_fallback_with_exclude(self, mock_conn):
        """Fallback COUNT in find_following uses $2::uuid[] (not $4)."""
        from app.repositories.social_repo import find_following

        user_id = uuid.uuid4()
        exclude_ids = [uuid.uuid4()]
        mock_conn.fetch = AsyncMock(return_value=[])
        mock_conn.fetchval = AsyncMock(return_value=2)

        result, total = await find_following(
            mock_conn, user_id, page=2, page_size=5, exclude_user_ids=exclude_ids
        )
        assert total == 2
        sql = mock_conn.fetchval.call_args[0][0]
        assert "$2::uuid[]" in sql
        assert "$4" not in sql

    @pytest.mark.anyio
    async def test_find_following_fallback_without_exclude(self, mock_conn):
        """Fallback COUNT in find_following works without exclude_user_ids."""
        from app.repositories.social_repo import find_following

        mock_conn.fetch = AsyncMock(return_value=[])
        mock_conn.fetchval = AsyncMock(return_value=4)

        result, total = await find_following(mock_conn, uuid.uuid4(), page=2, page_size=5)
        assert total == 4


# ===========================================================================
# B4: send_friend_request — block check inside transaction
# ===========================================================================


class TestSendFriendRequestBlockInTransaction:
    @patch(f"{_REPO}.insert_friendship", new_callable=AsyncMock)
    @patch(f"{_REPO}.find_friendship_between", new_callable=AsyncMock, return_value=None)
    @patch(f"{_REPO}.is_blocked", new_callable=AsyncMock, return_value=False)
    @patch("app.services.social.emit", new_callable=AsyncMock)
    @pytest.mark.anyio
    async def test_block_check_called_inside_transaction(
        self, mock_emit, mock_blocked, mock_find, mock_insert, mock_pool, mock_conn
    ):
        """is_blocked is called within the transaction context."""
        from app.services.social import send_friend_request

        requester = uuid.uuid4()
        addressee = uuid.uuid4()
        mock_insert.return_value = _make_friendship(requester, addressee)

        # Track call order
        call_order = []
        original_transaction = mock_conn.transaction

        tx = AsyncMock()
        tx.__aenter__ = AsyncMock(return_value=tx)
        tx.__aexit__ = AsyncMock(return_value=False)

        def track_transaction():
            call_order.append("transaction_start")
            return tx

        mock_conn.transaction = MagicMock(side_effect=track_transaction)

        original_is_blocked = mock_blocked.side_effect

        async def track_blocked(*args, **kwargs):
            call_order.append("is_blocked")
            return False

        mock_blocked.side_effect = track_blocked

        await send_friend_request(mock_pool, requester, addressee)

        # is_blocked must be called AFTER transaction starts
        assert call_order.index("transaction_start") < call_order.index("is_blocked")

    @patch(f"{_REPO}.is_blocked", new_callable=AsyncMock, return_value=True)
    @pytest.mark.anyio
    async def test_blocked_raises_inside_transaction(self, mock_blocked, mock_pool, mock_conn):
        """Block check inside transaction raises AppError and rolls back."""
        from app.services.social import send_friend_request

        with pytest.raises(AppError, match="Cannot interact"):
            await send_friend_request(mock_pool, uuid.uuid4(), uuid.uuid4())
        mock_conn.transaction.assert_called_once()


# ===========================================================================
# B5: DM send_message — block+friendship checks inside transaction
# ===========================================================================


class TestDMSendMessageTransactionChecks:
    @patch("app.core.database.get_pool")
    @patch(f"{_REPO}.is_blocked", new_callable=AsyncMock, return_value=True)
    @pytest.mark.anyio
    async def test_dm_block_check_in_transaction(self, mock_blocked, mock_get_pool, mock_pool, mock_conn):
        """DM send_message runs block check inside a transaction."""
        from app.services.dm import send_message

        mock_get_pool.return_value = mock_pool
        sender = str(uuid.uuid4())
        recipient = str(uuid.uuid4())

        with pytest.raises(AppError, match="Cannot message"):
            await send_message(sender, recipient, content="hello")

        # Verify transaction was opened
        mock_conn.transaction.assert_called_once()

    @patch("app.core.database.get_pool")
    @patch(f"{_DM_REPO}.get_dm_friends_only", new_callable=AsyncMock, return_value=True)
    @patch(f"{_REPO}.find_friendship_between", new_callable=AsyncMock, return_value=None)
    @patch(f"{_REPO}.is_blocked", new_callable=AsyncMock, return_value=False)
    @pytest.mark.anyio
    async def test_dm_friends_only_check_in_transaction(
        self, mock_blocked, mock_friendship, mock_dm_pref, mock_get_pool, mock_pool, mock_conn
    ):
        """DM friends-only check runs inside the same transaction as block check."""
        from app.services.dm import send_message

        mock_get_pool.return_value = mock_pool

        with pytest.raises(AppError, match="only accepts messages from friends"):
            await send_message(str(uuid.uuid4()), str(uuid.uuid4()), content="hi")

        # Transaction was used for the entire permission check
        mock_conn.transaction.assert_called_once()


# ===========================================================================
# B6: Recommendations exclude blocked users
# ===========================================================================


class TestRecommendationsExcludeBlocked:
    @pytest.mark.anyio
    async def test_find_recommendations_sql_excludes_blocked(self):
        """find_recommendations SQL includes NOT EXISTS for blocks table."""
        conn = AsyncMock()
        conn.fetch = AsyncMock(return_value=[])

        from app.repositories.recommendation_repo import find_recommendations

        await find_recommendations(conn, uuid.uuid4())
        sql = conn.fetch.call_args[0][0]
        assert "blocks" in sql
        assert "NOT EXISTS" in sql
        # Bilateral check: both directions
        assert "blocker_id = $1" in sql
        assert "blocked_id = $1" in sql
