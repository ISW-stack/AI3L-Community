"""Tests for social service — friendships, follows, blocks."""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def _make_friendship(
    requester_id: uuid.UUID | None = None,
    addressee_id: uuid.UUID | None = None,
    status: str = "PENDING",
    friendship_id: uuid.UUID | None = None,
) -> dict:
    now = datetime.now(timezone.utc)
    return {
        "id": friendship_id or uuid.uuid4(),
        "requester_id": requester_id or uuid.uuid4(),
        "addressee_id": addressee_id or uuid.uuid4(),
        "status": status,
        "created_at": now,
        "updated_at": now,
    }


def _make_follow_row(user_id: uuid.UUID | None = None) -> dict:
    now = datetime.now(timezone.utc)
    uid = user_id or uuid.uuid4()
    return {
        "id": uuid.uuid4(),
        "user_id": uid,
        "username": "testuser",
        "display_name": "Test User",
        "avatar_url": None,
        "created_at": now,
    }


def _make_friend_row(friend_id: uuid.UUID | None = None) -> dict:
    now = datetime.now(timezone.utc)
    fid = friend_id or uuid.uuid4()
    return {
        "id": uuid.uuid4(),
        "friend_id": fid,
        "username": "friend_user",
        "display_name": "Friend",
        "avatar_url": None,
        "affiliation": None,
        "created_at": now,
    }


def _make_block_row(blocked_id: uuid.UUID | None = None) -> dict:
    now = datetime.now(timezone.utc)
    return {
        "id": uuid.uuid4(),
        "blocked_id": blocked_id or uuid.uuid4(),
        "username": "blocked_user",
        "display_name": "Blocked",
        "avatar_url": None,
        "created_at": now,
    }


def _make_request_row(requester_id: uuid.UUID, addressee_id: uuid.UUID) -> dict:
    now = datetime.now(timezone.utc)
    return {
        "id": uuid.uuid4(),
        "requester_id": requester_id,
        "requester_username": "requester",
        "requester_display_name": "Requester",
        "requester_avatar_url": None,
        "addressee_id": addressee_id,
        "addressee_username": "addressee",
        "addressee_display_name": "Addressee",
        "addressee_avatar_url": None,
        "status": "PENDING",
        "created_at": now,
    }


_REPO = "app.repositories.social_repo"


# ── Friend Request ──────────────────────────────────────────────────


class TestSendFriendRequest:
    @patch(f"{_REPO}.insert_friendship", new_callable=AsyncMock)
    @patch(f"{_REPO}.find_friendship_between", new_callable=AsyncMock, return_value=None)
    @patch(f"{_REPO}.is_blocked", new_callable=AsyncMock, return_value=False)
    @patch("app.services.social.emit", new_callable=AsyncMock)
    async def test_send_success(
        self, mock_emit, mock_blocked, mock_find, mock_insert, mock_pool, mock_conn
    ):
        from app.services.social import send_friend_request

        requester = uuid.uuid4()
        addressee = uuid.uuid4()
        friendship = _make_friendship(requester, addressee)
        mock_insert.return_value = friendship

        result = await send_friend_request(mock_pool, requester, addressee)
        assert result["requester_id"] == requester
        mock_insert.assert_called_once()
        mock_emit.assert_called_once()

    async def test_self_request_error(self, mock_pool):
        from app.services.social import send_friend_request

        uid = uuid.uuid4()
        with pytest.raises(Exception, match="yourself"):
            await send_friend_request(mock_pool, uid, uid)

    @patch(f"{_REPO}.is_blocked", new_callable=AsyncMock, return_value=True)
    async def test_blocked_user_error(self, mock_blocked, mock_pool, mock_conn):
        from app.services.social import send_friend_request

        with pytest.raises(Exception, match="Cannot interact"):
            await send_friend_request(mock_pool, uuid.uuid4(), uuid.uuid4())

    @patch(f"{_REPO}.find_friendship_between", new_callable=AsyncMock)
    @patch(f"{_REPO}.is_blocked", new_callable=AsyncMock, return_value=False)
    async def test_already_friends_error(self, mock_blocked, mock_find, mock_pool, mock_conn):
        from app.services.social import send_friend_request

        requester = uuid.uuid4()
        addressee = uuid.uuid4()
        mock_find.return_value = _make_friendship(requester, addressee, "ACCEPTED")

        with pytest.raises(Exception, match="Already friends"):
            await send_friend_request(mock_pool, requester, addressee)

    @patch(f"{_REPO}.insert_follow", new_callable=AsyncMock, return_value={})
    @patch(f"{_REPO}.is_following", new_callable=AsyncMock, return_value=False)
    @patch(f"{_REPO}.accept_friendship", new_callable=AsyncMock)
    @patch(f"{_REPO}.find_friendship_between", new_callable=AsyncMock)
    @patch(f"{_REPO}.is_blocked", new_callable=AsyncMock, return_value=False)
    @patch("app.services.social.emit", new_callable=AsyncMock)
    async def test_reverse_pending_auto_accept(
        self,
        mock_emit,
        mock_blocked,
        mock_find,
        mock_accept,
        mock_is_follow,
        mock_insert_follow,
        mock_pool,
        mock_conn,
    ):
        from app.services.social import send_friend_request

        requester = uuid.uuid4()
        addressee = uuid.uuid4()
        # Existing PENDING where addressee is requester (reverse)
        existing = _make_friendship(addressee, requester, "PENDING")
        mock_find.return_value = existing
        accepted = _make_friendship(addressee, requester, "ACCEPTED")
        mock_accept.return_value = accepted

        result = await send_friend_request(mock_pool, requester, addressee)
        assert result["status"] == "ACCEPTED"
        mock_accept.assert_called_once()
        mock_emit.assert_called_once()

    @patch(f"{_REPO}.find_friendship_between", new_callable=AsyncMock)
    @patch(f"{_REPO}.is_blocked", new_callable=AsyncMock, return_value=False)
    async def test_duplicate_pending_error(self, mock_blocked, mock_find, mock_pool, mock_conn):
        from app.services.social import send_friend_request

        requester = uuid.uuid4()
        addressee = uuid.uuid4()
        mock_find.return_value = _make_friendship(requester, addressee, "PENDING")

        with pytest.raises(Exception, match="already sent"):
            await send_friend_request(mock_pool, requester, addressee)


class TestAcceptFriendRequest:
    @patch(f"{_REPO}.insert_follow", new_callable=AsyncMock, return_value={})
    @patch(f"{_REPO}.is_following", new_callable=AsyncMock, return_value=False)
    @patch(f"{_REPO}.accept_friendship", new_callable=AsyncMock)
    @patch(f"{_REPO}.find_friendship_by_id_for_update", new_callable=AsyncMock)
    @patch("app.services.social.emit", new_callable=AsyncMock)
    async def test_accept_success(
        self,
        mock_emit,
        mock_find,
        mock_accept,
        mock_is_follow,
        mock_insert_follow,
        mock_pool,
        mock_conn,
    ):
        from app.services.social import accept_friend_request

        user_id = uuid.uuid4()
        friendship_id = uuid.uuid4()
        friendship = _make_friendship(uuid.uuid4(), user_id, "PENDING", friendship_id)
        mock_find.return_value = friendship
        accepted = {**friendship, "status": "ACCEPTED"}
        mock_accept.return_value = accepted

        result = await accept_friend_request(mock_pool, friendship_id, user_id)
        assert result["status"] == "ACCEPTED"
        # Auto-follow both directions
        assert mock_insert_follow.call_count == 2

    @patch(f"{_REPO}.find_friendship_by_id_for_update", new_callable=AsyncMock, return_value=None)
    async def test_not_found(self, mock_find, mock_pool, mock_conn):
        from app.services.social import accept_friend_request

        with pytest.raises(Exception, match="not found"):
            await accept_friend_request(mock_pool, uuid.uuid4(), uuid.uuid4())

    @patch(f"{_REPO}.find_friendship_by_id_for_update", new_callable=AsyncMock)
    async def test_not_addressee(self, mock_find, mock_pool, mock_conn):
        from app.services.social import accept_friend_request

        user_id = uuid.uuid4()
        other = uuid.uuid4()
        friendship = _make_friendship(other, uuid.uuid4(), "PENDING")
        mock_find.return_value = friendship

        with pytest.raises(Exception, match="addressee"):
            await accept_friend_request(mock_pool, friendship["id"], user_id)


class TestRejectFriendRequest:
    @patch(f"{_REPO}.reject_friendship", new_callable=AsyncMock, return_value=True)
    @patch(f"{_REPO}.find_friendship_by_id_for_update", new_callable=AsyncMock)
    async def test_reject_success(self, mock_find, mock_reject, mock_pool, mock_conn):
        from app.services.social import reject_friend_request

        user_id = uuid.uuid4()
        friendship_id = uuid.uuid4()
        friendship = _make_friendship(uuid.uuid4(), user_id, "PENDING", friendship_id)
        mock_find.return_value = friendship

        await reject_friend_request(mock_pool, friendship_id, user_id)
        mock_reject.assert_called_once()


class TestUnfriend:
    @patch(f"{_REPO}.delete_friendship_between", new_callable=AsyncMock, return_value=True)
    async def test_unfriend_success(self, mock_delete, mock_pool, mock_conn):
        from app.services.social import unfriend

        await unfriend(mock_pool, uuid.uuid4(), uuid.uuid4())
        mock_delete.assert_called_once()

    @patch(f"{_REPO}.delete_friendship_between", new_callable=AsyncMock, return_value=False)
    async def test_unfriend_not_found(self, mock_delete, mock_pool, mock_conn):
        from app.services.social import unfriend

        with pytest.raises(Exception, match="not found"):
            await unfriend(mock_pool, uuid.uuid4(), uuid.uuid4())


# ── Follow ──────────────────────────────────────────────────────────


class TestFollowUser:
    @patch(f"{_REPO}.insert_follow", new_callable=AsyncMock, return_value={})
    @patch(f"{_REPO}.is_following", new_callable=AsyncMock, return_value=False)
    @patch(f"{_REPO}.is_blocked", new_callable=AsyncMock, return_value=False)
    async def test_follow_success(
        self, mock_blocked, mock_is_follow, mock_insert, mock_pool, mock_conn
    ):
        from app.services.social import follow_user

        result = await follow_user(mock_pool, uuid.uuid4(), uuid.uuid4())
        mock_insert.assert_called_once()

    async def test_follow_self_error(self, mock_pool):
        from app.services.social import follow_user

        uid = uuid.uuid4()
        with pytest.raises(Exception, match="yourself"):
            await follow_user(mock_pool, uid, uid)

    @patch(f"{_REPO}.is_blocked", new_callable=AsyncMock, return_value=True)
    async def test_follow_blocked_error(self, mock_blocked, mock_pool, mock_conn):
        from app.services.social import follow_user

        with pytest.raises(Exception, match="Cannot interact"):
            await follow_user(mock_pool, uuid.uuid4(), uuid.uuid4())


class TestUnfollowUser:
    @patch(f"{_REPO}.delete_follow", new_callable=AsyncMock, return_value=True)
    async def test_unfollow_success(self, mock_delete, mock_pool, mock_conn):
        from app.services.social import unfollow_user

        await unfollow_user(mock_pool, uuid.uuid4(), uuid.uuid4())
        mock_delete.assert_called_once()

    @patch(f"{_REPO}.delete_follow", new_callable=AsyncMock, return_value=False)
    async def test_unfollow_not_found(self, mock_delete, mock_pool, mock_conn):
        from app.services.social import unfollow_user

        with pytest.raises(Exception, match="Not following"):
            await unfollow_user(mock_pool, uuid.uuid4(), uuid.uuid4())


# ── Block ───────────────────────────────────────────────────────────


class TestBlockUser:
    @patch("app.services.social.update_block_cache", new_callable=AsyncMock)
    @patch(f"{_REPO}.insert_block", new_callable=AsyncMock)
    @patch(f"{_REPO}.delete_follows_between", new_callable=AsyncMock)
    @patch(f"{_REPO}.delete_friendship_between", new_callable=AsyncMock)
    @patch(f"{_REPO}.count_blocks", new_callable=AsyncMock, return_value=0)
    async def test_block_success(
        self,
        mock_count,
        mock_del_friend,
        mock_del_follow,
        mock_insert_block,
        mock_cache,
        mock_pool,
        mock_conn,
        mock_redis,
    ):
        from app.services.social import block_user

        block_row = _make_block_row()
        mock_insert_block.return_value = block_row

        result = await block_user(mock_pool, mock_redis, uuid.uuid4(), uuid.uuid4())
        mock_del_friend.assert_called_once()
        mock_del_follow.assert_called_once()
        mock_insert_block.assert_called_once()
        mock_cache.assert_called_once()

    async def test_block_self_error(self, mock_pool, mock_redis):
        from app.services.social import block_user

        uid = uuid.uuid4()
        with pytest.raises(Exception, match="yourself"):
            await block_user(mock_pool, mock_redis, uid, uid)

    @patch(f"{_REPO}.count_blocks", new_callable=AsyncMock, return_value=5)
    async def test_block_limit_error(self, mock_count, mock_pool, mock_conn, mock_redis):
        from app.services.social import block_user

        with pytest.raises(Exception, match="limit"):
            await block_user(mock_pool, mock_redis, uuid.uuid4(), uuid.uuid4())


class TestUnblockUser:
    @patch("app.services.social.update_block_cache", new_callable=AsyncMock)
    @patch(f"{_REPO}.delete_block", new_callable=AsyncMock, return_value=True)
    async def test_unblock_success(self, mock_delete, mock_cache, mock_pool, mock_conn, mock_redis):
        from app.services.social import unblock_user

        await unblock_user(mock_pool, mock_redis, uuid.uuid4(), uuid.uuid4())
        mock_delete.assert_called_once()
        mock_cache.assert_called_once()

    @patch(f"{_REPO}.delete_block", new_callable=AsyncMock, return_value=False)
    async def test_unblock_not_found(self, mock_delete, mock_pool, mock_conn, mock_redis):
        from app.services.social import unblock_user

        with pytest.raises(Exception, match="not found"):
            await unblock_user(mock_pool, mock_redis, uuid.uuid4(), uuid.uuid4())


# ── List endpoints ──────────────────────────────────────────────────


class TestListFriends:
    @patch(f"{_REPO}.find_friends", new_callable=AsyncMock)
    async def test_list_friends(self, mock_find, mock_pool, mock_conn):
        from app.services.social import list_friends

        friend_row = _make_friend_row()
        mock_find.return_value = ([friend_row], 1)

        rows, total = await list_friends(mock_pool, uuid.uuid4())
        assert total == 1
        assert len(rows) == 1


class TestListFollowers:
    @patch(f"{_REPO}.find_followers", new_callable=AsyncMock)
    async def test_list_followers(self, mock_find, mock_pool, mock_conn):
        from app.services.social import list_followers

        follow_row = _make_follow_row()
        mock_find.return_value = ([follow_row], 1)

        rows, total = await list_followers(mock_pool, uuid.uuid4())
        assert total == 1


class TestListFollowing:
    @patch(f"{_REPO}.find_following", new_callable=AsyncMock)
    async def test_list_following(self, mock_find, mock_pool, mock_conn):
        from app.services.social import list_following

        follow_row = _make_follow_row()
        mock_find.return_value = ([follow_row], 1)

        rows, total = await list_following(mock_pool, uuid.uuid4())
        assert total == 1


# ── Bug Fix Tests ──────────────────────────────────────────────────


class TestAcceptFriendRequestTOCTOU:
    """H4: Verify accept_friend_request uses FOR UPDATE to prevent TOCTOU."""

    @patch(f"{_REPO}.insert_follow", new_callable=AsyncMock, return_value={})
    @patch(f"{_REPO}.is_following", new_callable=AsyncMock, return_value=False)
    @patch(f"{_REPO}.accept_friendship", new_callable=AsyncMock)
    @patch(f"{_REPO}.find_friendship_by_id_for_update", new_callable=AsyncMock)
    @patch("app.services.social.emit", new_callable=AsyncMock)
    async def test_accept_uses_for_update_in_transaction(
        self,
        mock_emit,
        mock_find_for_update,
        mock_accept,
        mock_is_follow,
        mock_insert_follow,
        mock_pool,
        mock_conn,
    ):
        """accept_friend_request must call find_friendship_by_id_for_update
        (which uses SELECT ... FOR UPDATE) inside a transaction."""
        from app.services.social import accept_friend_request

        user_id = uuid.uuid4()
        friendship_id = uuid.uuid4()
        friendship = _make_friendship(uuid.uuid4(), user_id, "PENDING", friendship_id)
        mock_find_for_update.return_value = friendship
        mock_accept.return_value = {**friendship, "status": "ACCEPTED"}

        await accept_friend_request(mock_pool, friendship_id, user_id)

        # Verify FOR UPDATE variant was called (not plain find_friendship_by_id)
        mock_find_for_update.assert_called_once_with(mock_conn, friendship_id)
        # Verify transaction was opened
        mock_conn.transaction.assert_called_once()


class TestDeleteFriendshipBetweenResult:
    """M2: Verify delete_friendship_between correctly handles 'DELETE 0'."""

    async def test_delete_zero_returns_false(self, mock_conn):
        from app.repositories.social_repo import delete_friendship_between

        mock_conn.execute = AsyncMock(return_value="DELETE 0")
        result = await delete_friendship_between(mock_conn, uuid.uuid4(), uuid.uuid4())
        assert result is False

    async def test_delete_one_returns_true(self, mock_conn):
        from app.repositories.social_repo import delete_friendship_between

        mock_conn.execute = AsyncMock(return_value="DELETE 1")
        result = await delete_friendship_between(mock_conn, uuid.uuid4(), uuid.uuid4())
        assert result is True


class TestAcceptFriendshipNoneCheck:
    """M3: Verify accept_friend_request raises when accept_friendship returns None."""

    @patch(f"{_REPO}.find_friendship_by_id_for_update", new_callable=AsyncMock)
    @patch(f"{_REPO}.accept_friendship", new_callable=AsyncMock, return_value=None)
    async def test_accept_returns_none_raises(
        self,
        mock_accept,
        mock_find,
        mock_pool,
        mock_conn,
    ):
        from app.services.social import accept_friend_request

        user_id = uuid.uuid4()
        friendship_id = uuid.uuid4()
        friendship = _make_friendship(uuid.uuid4(), user_id, "PENDING", friendship_id)
        mock_find.return_value = friendship

        with pytest.raises(Exception, match="not found or already processed"):
            await accept_friend_request(mock_pool, friendship_id, user_id)


class TestBlacklistFilterFollowers:
    """M4: Verify blacklist filtering in followers listing."""

    @patch(f"{_REPO}.find_followers", new_callable=AsyncMock)
    @patch("app.services.social.get_blocked_user_ids", new_callable=AsyncMock)
    async def test_followers_exclude_blocked_users(
        self,
        mock_get_blocked,
        mock_find,
        mock_pool,
        mock_conn,
        mock_redis,
    ):
        from app.services.social import list_followers

        blocked_uid = uuid.uuid4()
        mock_get_blocked.return_value = {str(blocked_uid)}
        mock_find.return_value = ([], 0)

        user_id = uuid.uuid4()
        await list_followers(mock_pool, user_id, redis=mock_redis)

        # Verify find_followers was called with exclude_user_ids containing blocked UUID
        call_kwargs = mock_find.call_args
        assert call_kwargs[1]["exclude_user_ids"] == [blocked_uid]

    @patch(f"{_REPO}.find_followers", new_callable=AsyncMock)
    async def test_followers_no_redis_no_exclusion(
        self,
        mock_find,
        mock_pool,
        mock_conn,
    ):
        from app.services.social import list_followers

        mock_find.return_value = ([], 0)
        await list_followers(mock_pool, uuid.uuid4())

        # Without redis, exclude_user_ids should be None
        call_kwargs = mock_find.call_args
        assert call_kwargs[1]["exclude_user_ids"] is None


class TestBlacklistFilterFollowing:
    """M4: Verify blacklist filtering in following listing."""

    @patch(f"{_REPO}.find_following", new_callable=AsyncMock)
    @patch("app.services.social.get_blocked_user_ids", new_callable=AsyncMock)
    async def test_following_exclude_blocked_users(
        self,
        mock_get_blocked,
        mock_find,
        mock_pool,
        mock_conn,
        mock_redis,
    ):
        from app.services.social import list_following

        blocked_uid = uuid.uuid4()
        mock_get_blocked.return_value = {str(blocked_uid)}
        mock_find.return_value = ([], 0)

        user_id = uuid.uuid4()
        await list_following(mock_pool, user_id, redis=mock_redis)

        # Verify find_following was called with exclude_user_ids containing blocked UUID
        call_kwargs = mock_find.call_args
        assert call_kwargs[1]["exclude_user_ids"] == [blocked_uid]

    @patch(f"{_REPO}.find_following", new_callable=AsyncMock)
    async def test_following_no_redis_no_exclusion(
        self,
        mock_find,
        mock_pool,
        mock_conn,
    ):
        from app.services.social import list_following

        mock_find.return_value = ([], 0)
        await list_following(mock_pool, uuid.uuid4())

        # Without redis, exclude_user_ids should be None
        call_kwargs = mock_find.call_args
        assert call_kwargs[1]["exclude_user_ids"] is None


class TestRejectFriendRequestAtomicity:
    """M11: Verify reject_friend_request uses FOR UPDATE in a transaction."""

    @patch(f"{_REPO}.reject_friendship", new_callable=AsyncMock, return_value=True)
    @patch(f"{_REPO}.find_friendship_by_id_for_update", new_callable=AsyncMock)
    async def test_reject_uses_for_update_in_transaction(
        self,
        mock_find_for_update,
        mock_reject,
        mock_pool,
        mock_conn,
    ):
        from app.services.social import reject_friend_request

        user_id = uuid.uuid4()
        friendship_id = uuid.uuid4()
        friendship = _make_friendship(uuid.uuid4(), user_id, "PENDING", friendship_id)
        mock_find_for_update.return_value = friendship

        await reject_friend_request(mock_pool, friendship_id, user_id)

        # Verify FOR UPDATE variant was called (not plain find_friendship_by_id)
        mock_find_for_update.assert_called_once_with(mock_conn, friendship_id)
        # Verify transaction was opened
        mock_conn.transaction.assert_called_once()
        # Verify delete happened
        mock_reject.assert_called_once_with(mock_conn, friendship_id)


class TestEmptyPageReturnsActualTotal:
    """L2: Verify empty pages return correct total count, not 0."""

    async def test_find_friends_empty_page_returns_total(self, mock_conn):
        from app.repositories.social_repo import find_friends

        # Empty rows (e.g., page 2 with only 1 result total)
        mock_conn.fetch = AsyncMock(return_value=[])
        mock_conn.fetchval = AsyncMock(return_value=5)

        rows, total = await find_friends(mock_conn, uuid.uuid4(), page=2, page_size=20)
        assert rows == []
        assert total == 5
        # Verify the COUNT query was executed
        mock_conn.fetchval.assert_called_once()

    async def test_find_followers_empty_page_returns_total(self, mock_conn):
        from app.repositories.social_repo import find_followers

        mock_conn.fetch = AsyncMock(return_value=[])
        mock_conn.fetchval = AsyncMock(return_value=3)

        rows, total = await find_followers(mock_conn, uuid.uuid4(), page=2, page_size=20)
        assert rows == []
        assert total == 3

    async def test_find_following_empty_page_returns_total(self, mock_conn):
        from app.repositories.social_repo import find_following

        mock_conn.fetch = AsyncMock(return_value=[])
        mock_conn.fetchval = AsyncMock(return_value=7)

        rows, total = await find_following(mock_conn, uuid.uuid4(), page=2, page_size=20)
        assert rows == []
        assert total == 7

    async def test_find_blocks_empty_page_returns_total(self, mock_conn):
        from app.repositories.social_repo import find_blocks

        mock_conn.fetch = AsyncMock(return_value=[])
        mock_conn.fetchval = AsyncMock(return_value=2)

        rows, total = await find_blocks(mock_conn, uuid.uuid4(), page=2, page_size=20)
        assert rows == []
        assert total == 2


class TestListBlocks:
    @patch(f"{_REPO}.find_blocks", new_callable=AsyncMock)
    async def test_list_blocks(self, mock_find, mock_pool, mock_conn):
        from app.services.social import list_blocks

        block_row = _make_block_row()
        mock_find.return_value = ([block_row], 1)

        rows, total = await list_blocks(mock_pool, uuid.uuid4())
        assert total == 1


# ── Relationship Status ─────────────────────────────────────────────


class TestRelationshipStatus:
    @patch(f"{_REPO}.get_relationship_status", new_callable=AsyncMock)
    async def test_get_status(self, mock_status, mock_pool, mock_conn):
        from app.services.social import get_relationship_status

        mock_status.return_value = {
            "is_friend": True,
            "is_following": True,
            "is_followed_by": False,
            "is_blocked": False,
            "pending_request": None,
            "friendship_id": str(uuid.uuid4()),
        }

        result = await get_relationship_status(mock_pool, uuid.uuid4(), uuid.uuid4())
        assert result["is_friend"] is True
        assert result["is_following"] is True
