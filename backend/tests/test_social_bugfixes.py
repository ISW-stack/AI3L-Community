"""Tests for social/friend/DM/recommendation bugfixes.

Covers:
- B1: find_pending_requests fallback COUNT on empty page
- B2: find_pending_requests filters deleted users
- B3: find_followers/find_following fallback COUNT uses correct $2 param
- B4: send_friend_request block check inside transaction
- B5: DM send_message block+friendship checks inside transaction
- B6: Recommendations exclude blocked users
- B7: reject_friend_request_endpoint applies rate limit
- B8: count_blocks excludes soft-deleted blocked users
- B9: count_friends excludes soft-deleted friends
- B10: count_followers/count_following exclude soft-deleted users
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


# ===========================================================================
# B7: reject_friend_request_endpoint — must apply rate limit
# ===========================================================================


class TestRejectFriendRequestEndpointRateLimit:
    @pytest.mark.anyio
    async def test_reject_endpoint_enforces_rate_limit(self, client):
        """PUT /social/friends/{id}/reject returns 429 when rate limit is exceeded."""
        from app.core.deps import get_current_user
        from app.main import app

        user_id = str(uuid.uuid4())
        app.dependency_overrides[get_current_user] = lambda: {
            "sub": user_id,
            "role": "MEMBER",
            "jti": str(uuid.uuid4()),
        }
        try:
            with patch(
                "app.api.v1.endpoints.social.check_rate_limit",
                new_callable=AsyncMock,
                return_value=False,
            ):
                resp = await client.put(
                    f"/api/v1/social/friends/{uuid.uuid4()}/reject",
                )
            assert resp.status_code == 429
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.anyio
    async def test_reject_endpoint_uses_social_rate_limit_key(self, client):
        """reject endpoint uses social:reject:{user_id} as rate limit key."""
        from app.core.deps import get_current_user
        from app.main import app

        user_id = str(uuid.uuid4())
        app.dependency_overrides[get_current_user] = lambda: {
            "sub": user_id,
            "role": "MEMBER",
            "jti": str(uuid.uuid4()),
        }
        captured_keys: list[str] = []

        async def capture_rate_limit(key: str, *args, **kwargs) -> bool:
            captured_keys.append(key)
            return False  # trigger 429 to short-circuit

        try:
            with patch("app.api.v1.endpoints.social.check_rate_limit", side_effect=capture_rate_limit):
                await client.put(
                    f"/api/v1/social/friends/{uuid.uuid4()}/reject",
                )
            assert any(k.startswith("social:reject:") for k in captured_keys), (
                f"Expected 'social:reject:' key, got: {captured_keys}"
            )
            assert any(user_id in k for k in captured_keys)
        finally:
            app.dependency_overrides.clear()


# ===========================================================================
# B8: count_blocks — must exclude soft-deleted blocked users
# ===========================================================================


class TestCountBlocksExcludesDeleted:
    @pytest.mark.anyio
    async def test_count_blocks_sql_joins_users_and_filters_deleted(self, mock_conn):
        """count_blocks SQL joins users table and filters is_deleted = false."""
        from app.repositories.social_repo import count_blocks

        mock_conn.fetchval = AsyncMock(return_value=3)

        await count_blocks(mock_conn, uuid.uuid4())

        sql = mock_conn.fetchval.call_args[0][0]
        assert "JOIN users" in sql
        assert "is_deleted = false" in sql

    @pytest.mark.anyio
    async def test_count_blocks_deleted_user_not_counted(self, mock_conn):
        """count_blocks returns the DB value (soft-deleted users filtered by SQL)."""
        from app.repositories.social_repo import count_blocks

        # DB returns 2 (after filtering soft-deleted)
        mock_conn.fetchval = AsyncMock(return_value=2)

        result = await count_blocks(mock_conn, uuid.uuid4())
        assert result == 2


# ===========================================================================
# B9: count_friends — must exclude soft-deleted friends
# ===========================================================================


class TestCountFriendsExcludesDeleted:
    @pytest.mark.anyio
    async def test_count_friends_sql_joins_users_and_filters_deleted(self, mock_conn):
        """count_friends SQL joins users table to exclude soft-deleted friends."""
        from app.repositories.social_repo import count_friends

        mock_conn.fetchval = AsyncMock(return_value=5)

        await count_friends(mock_conn, uuid.uuid4())

        sql = mock_conn.fetchval.call_args[0][0]
        assert "JOIN users" in sql
        assert "is_deleted = false" in sql

    @pytest.mark.anyio
    async def test_count_friends_returns_db_value(self, mock_conn):
        """count_friends returns the integer result from DB."""
        from app.repositories.social_repo import count_friends

        mock_conn.fetchval = AsyncMock(return_value=4)

        result = await count_friends(mock_conn, uuid.uuid4())
        assert result == 4


# ===========================================================================
# B10: count_followers / count_following — must exclude soft-deleted users
# ===========================================================================


class TestCountFollowersFollowingExcludeDeleted:
    @pytest.mark.anyio
    async def test_count_followers_sql_joins_users_and_filters_deleted(self, mock_conn):
        """count_followers SQL joins users table and filters is_deleted = false."""
        from app.repositories.social_repo import count_followers

        mock_conn.fetchval = AsyncMock(return_value=10)

        await count_followers(mock_conn, uuid.uuid4())

        sql = mock_conn.fetchval.call_args[0][0]
        assert "JOIN users" in sql
        assert "is_deleted = false" in sql

    @pytest.mark.anyio
    async def test_count_following_sql_joins_users_and_filters_deleted(self, mock_conn):
        """count_following SQL joins users table and filters is_deleted = false."""
        from app.repositories.social_repo import count_following

        mock_conn.fetchval = AsyncMock(return_value=7)

        await count_following(mock_conn, uuid.uuid4())

        sql = mock_conn.fetchval.call_args[0][0]
        assert "JOIN users" in sql
        assert "is_deleted = false" in sql

    @pytest.mark.anyio
    async def test_count_followers_returns_db_value(self, mock_conn):
        """count_followers returns the integer from DB."""
        from app.repositories.social_repo import count_followers

        mock_conn.fetchval = AsyncMock(return_value=3)
        assert await count_followers(mock_conn, uuid.uuid4()) == 3

    @pytest.mark.anyio
    async def test_count_following_returns_db_value(self, mock_conn):
        """count_following returns the integer from DB."""
        from app.repositories.social_repo import count_following

        mock_conn.fetchval = AsyncMock(return_value=6)
        assert await count_following(mock_conn, uuid.uuid4()) == 6


# ===========================================================================
# M1: is_following — must exclude soft-deleted users
# ===========================================================================


class TestIsFollowingExcludesDeleted:
    @pytest.mark.anyio
    async def test_is_following_returns_false_for_deleted_user(self, mock_conn):
        """is_following returns False when the followed user is soft-deleted."""
        from app.repositories.social_repo import is_following

        # DB returns 0 because the JOIN + is_deleted=false filters out the row
        mock_conn.fetchval = AsyncMock(return_value=0)

        result = await is_following(mock_conn, uuid.uuid4(), uuid.uuid4())
        assert result is False

    @pytest.mark.anyio
    async def test_is_following_sql_joins_users_and_filters_deleted(self, mock_conn):
        """is_following SQL must join users and include is_deleted = false."""
        from app.repositories.social_repo import is_following

        mock_conn.fetchval = AsyncMock(return_value=0)

        await is_following(mock_conn, uuid.uuid4(), uuid.uuid4())

        sql = mock_conn.fetchval.call_args[0][0]
        assert "JOIN users" in sql
        assert "is_deleted = false" in sql

    @pytest.mark.anyio
    async def test_is_following_returns_true_for_active_user(self, mock_conn):
        """is_following returns True when a valid follow exists with active user."""
        from app.repositories.social_repo import is_following

        mock_conn.fetchval = AsyncMock(return_value=1)

        result = await is_following(mock_conn, uuid.uuid4(), uuid.uuid4())
        assert result is True


# ===========================================================================
# M2: is_blocked — must exclude soft-deleted users
# ===========================================================================


class TestIsBlockedExcludesDeleted:
    @pytest.mark.anyio
    async def test_is_blocked_returns_false_when_blocker_deleted(self, mock_conn):
        """is_blocked returns False when the blocker is soft-deleted."""
        from app.repositories.social_repo import is_blocked

        # DB returns 0 because the JOIN filters out deleted blocker
        mock_conn.fetchval = AsyncMock(return_value=0)

        result = await is_blocked(mock_conn, uuid.uuid4(), uuid.uuid4())
        assert result is False

    @pytest.mark.anyio
    async def test_is_blocked_returns_false_when_blocked_deleted(self, mock_conn):
        """is_blocked returns False when the blocked user is soft-deleted."""
        from app.repositories.social_repo import is_blocked

        mock_conn.fetchval = AsyncMock(return_value=0)

        result = await is_blocked(mock_conn, uuid.uuid4(), uuid.uuid4())
        assert result is False

    @pytest.mark.anyio
    async def test_is_blocked_sql_joins_both_users_and_filters_deleted(self, mock_conn):
        """is_blocked SQL must join both blocker and blocked users and filter is_deleted."""
        from app.repositories.social_repo import is_blocked

        mock_conn.fetchval = AsyncMock(return_value=0)

        await is_blocked(mock_conn, uuid.uuid4(), uuid.uuid4())

        sql = mock_conn.fetchval.call_args[0][0]
        # Must join both user sides
        assert "u_blocker" in sql
        assert "u_blocked" in sql
        assert "u_blocker.is_deleted = false" in sql
        assert "u_blocked.is_deleted = false" in sql

    @pytest.mark.anyio
    async def test_is_blocked_returns_true_for_active_users(self, mock_conn):
        """is_blocked returns True when both users are active and block exists."""
        from app.repositories.social_repo import is_blocked

        mock_conn.fetchval = AsyncMock(return_value=1)

        result = await is_blocked(mock_conn, uuid.uuid4(), uuid.uuid4())
        assert result is True
