"""Tests for friend event handlers (H6) and block cache DB fallback (H7)."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ── H6: Friend event handlers ───────────────────────────────────────


@pytest.mark.anyio
async def test_friend_request_handler_creates_notification():
    """friend.request handler should create a notification for the target user."""
    from app.event_handlers import _on_friend_request

    requester_id = str(uuid.uuid4())
    target_id = str(uuid.uuid4())
    friendship_id = str(uuid.uuid4())

    with (
        patch("app.event_handlers._is_blocked", new_callable=AsyncMock, return_value=False),
        patch(
            "app.event_handlers._check_idempotent",
            new_callable=AsyncMock,
            return_value=True,
        ),
        patch(
            "app.services.notification.create_notification",
            new_callable=AsyncMock,
        ) as mock_create,
    ):
        await _on_friend_request(
            user_id=requester_id,
            target_id=target_id,
            friendship_id=friendship_id,
        )

        mock_create.assert_called_once_with(
            user_id=target_id,
            trigger_user_id=requester_id,
            action_type="FRIEND_REQUEST",
            entity_type="friendship",
            entity_id=friendship_id,
            message="You have a new friend request",
        )


@pytest.mark.anyio
async def test_friend_request_handler_skips_when_blocked():
    """friend.request handler should skip notification when target blocked requester."""
    from app.event_handlers import _on_friend_request

    with (
        patch("app.event_handlers._is_blocked", new_callable=AsyncMock, return_value=True),
        patch(
            "app.services.notification.create_notification",
            new_callable=AsyncMock,
        ) as mock_create,
    ):
        await _on_friend_request(
            user_id=str(uuid.uuid4()),
            target_id=str(uuid.uuid4()),
            friendship_id=str(uuid.uuid4()),
        )

        mock_create.assert_not_called()


@pytest.mark.anyio
async def test_friend_accepted_handler_creates_notification():
    """friend.accepted handler should create a notification for the requester."""
    from app.event_handlers import _on_friend_accepted

    requester_id = str(uuid.uuid4())
    friend_id = str(uuid.uuid4())
    friendship_id = str(uuid.uuid4())

    with (
        patch("app.event_handlers._is_blocked", new_callable=AsyncMock, return_value=False),
        patch(
            "app.event_handlers._check_idempotent",
            new_callable=AsyncMock,
            return_value=True,
        ),
        patch(
            "app.services.notification.create_notification",
            new_callable=AsyncMock,
        ) as mock_create,
    ):
        await _on_friend_accepted(
            user_id=requester_id,
            friend_id=friend_id,
            friendship_id=friendship_id,
        )

        mock_create.assert_called_once_with(
            user_id=requester_id,
            trigger_user_id=friend_id,
            action_type="FRIEND_ACCEPTED",
            entity_type="friendship",
            entity_id=friendship_id,
            message="Your friend request was accepted",
        )


@pytest.mark.anyio
async def test_friend_accepted_handler_skips_when_blocked():
    """friend.accepted handler should skip notification when users are blocked."""
    from app.event_handlers import _on_friend_accepted

    with (
        patch("app.event_handlers._is_blocked", new_callable=AsyncMock, return_value=True),
        patch(
            "app.services.notification.create_notification",
            new_callable=AsyncMock,
        ) as mock_create,
    ):
        await _on_friend_accepted(
            user_id=str(uuid.uuid4()),
            friend_id=str(uuid.uuid4()),
            friendship_id=str(uuid.uuid4()),
        )

        mock_create.assert_not_called()


@pytest.mark.anyio
async def test_friend_accepted_handler_skips_duplicate():
    """friend.accepted handler should skip when idempotency check fails."""
    from app.event_handlers import _on_friend_accepted

    with (
        patch("app.event_handlers._is_blocked", new_callable=AsyncMock, return_value=False),
        patch(
            "app.event_handlers._check_idempotent",
            new_callable=AsyncMock,
            return_value=False,
        ),
        patch(
            "app.services.notification.create_notification",
            new_callable=AsyncMock,
        ) as mock_create,
    ):
        await _on_friend_accepted(
            user_id=str(uuid.uuid4()),
            friend_id=str(uuid.uuid4()),
            friendship_id=str(uuid.uuid4()),
        )

        mock_create.assert_not_called()


@pytest.mark.anyio
async def test_friend_accepted_idempotent_key_uses_friendship_id():
    """friend.accepted idempotent key must include friendship_id so different
    friendships don't collide within the 5-minute dedup window."""
    from app.event_handlers import _on_friend_accepted

    requester_id = str(uuid.uuid4())
    friend_id_1 = str(uuid.uuid4())
    friend_id_2 = str(uuid.uuid4())
    fid_1 = str(uuid.uuid4())
    fid_2 = str(uuid.uuid4())

    idempotent_calls: list[tuple] = []

    async def track_idempotent(*args: object) -> bool:
        idempotent_calls.append(args)
        return True

    with (
        patch("app.event_handlers._is_blocked", new_callable=AsyncMock, return_value=False),
        patch("app.event_handlers._check_idempotent", side_effect=track_idempotent),
        patch(
            "app.services.notification.create_notification",
            new_callable=AsyncMock,
        ) as mock_create,
    ):
        await _on_friend_accepted(user_id=requester_id, friend_id=friend_id_1, friendship_id=fid_1)
        await _on_friend_accepted(user_id=requester_id, friend_id=friend_id_2, friendship_id=fid_2)

        # Both calls should use distinct friendship_id in the idempotent key
        assert len(idempotent_calls) == 2
        assert idempotent_calls[0] == (requester_id, "friendship", fid_1, "FRIEND_ACCEPTED")
        assert idempotent_calls[1] == (requester_id, "friendship", fid_2, "FRIEND_ACCEPTED")
        # Both notifications should be created (no false dedup)
        assert mock_create.call_count == 2


@pytest.mark.anyio
async def test_friend_accepted_notification_includes_entity_id():
    """friend.accepted notification must include friendship_id as entity_id
    so the frontend can link to the correct friendship."""
    from app.event_handlers import _on_friend_accepted

    requester_id = str(uuid.uuid4())
    friend_id = str(uuid.uuid4())
    friendship_id = str(uuid.uuid4())

    with (
        patch("app.event_handlers._is_blocked", new_callable=AsyncMock, return_value=False),
        patch(
            "app.event_handlers._check_idempotent",
            new_callable=AsyncMock,
            return_value=True,
        ),
        patch(
            "app.services.notification.create_notification",
            new_callable=AsyncMock,
        ) as mock_create,
    ):
        await _on_friend_accepted(
            user_id=requester_id,
            friend_id=friend_id,
            friendship_id=friendship_id,
        )

        call_kwargs = mock_create.call_args.kwargs
        assert call_kwargs["entity_id"] == friendship_id
        assert call_kwargs["entity_type"] == "friendship"


@pytest.mark.anyio
async def test_friend_request_handler_raises_on_create_failure():
    """friend.request handler should re-raise exceptions from create_notification
    so the event bus can retry."""
    from app.event_handlers import _on_friend_request

    with (
        patch("app.event_handlers._is_blocked", new_callable=AsyncMock, return_value=False),
        patch(
            "app.event_handlers._check_idempotent",
            new_callable=AsyncMock,
            return_value=True,
        ),
        patch(
            "app.services.notification.create_notification",
            new_callable=AsyncMock,
            side_effect=ConnectionError("Redis down"),
        ),
    ):
        with pytest.raises(ConnectionError):
            await _on_friend_request(
                user_id=str(uuid.uuid4()),
                target_id=str(uuid.uuid4()),
                friendship_id=str(uuid.uuid4()),
            )


@pytest.mark.anyio
async def test_friend_accepted_handler_raises_on_create_failure():
    """friend.accepted handler should re-raise exceptions from create_notification
    so the event bus can retry."""
    from app.event_handlers import _on_friend_accepted

    with (
        patch("app.event_handlers._is_blocked", new_callable=AsyncMock, return_value=False),
        patch(
            "app.event_handlers._check_idempotent",
            new_callable=AsyncMock,
            return_value=True,
        ),
        patch(
            "app.services.notification.create_notification",
            new_callable=AsyncMock,
            side_effect=ConnectionError("Redis down"),
        ),
    ):
        with pytest.raises(ConnectionError):
            await _on_friend_accepted(
                user_id=str(uuid.uuid4()),
                friend_id=str(uuid.uuid4()),
                friendship_id=str(uuid.uuid4()),
            )


def test_register_all_includes_friend_handlers():
    """register_all() should register friend.request and friend.accepted handlers."""
    from app.event_handlers import register_all

    with patch("app.event_handlers.on") as mock_on:
        register_all()

        registered_events = [call.args[0] for call in mock_on.call_args_list]
        assert "friend.request" in registered_events
        assert "friend.accepted" in registered_events


# ── H7: Block cache DB fallback ─────────────────────────────────────


@pytest.mark.anyio
async def test_get_blocked_user_ids_returns_from_redis():
    """get_blocked_user_ids should return Redis cached data when available."""
    from app.core.blacklist import get_blocked_user_ids

    other_id = str(uuid.uuid4())
    redis = AsyncMock()
    redis.smembers = AsyncMock(return_value={other_id})

    result = await get_blocked_user_ids(redis, str(uuid.uuid4()))

    assert result == {other_id}


@pytest.mark.anyio
async def test_get_blocked_user_ids_falls_back_to_db(mock_pool, mock_conn):
    """get_blocked_user_ids should query DB when Redis returns empty and pool is provided."""
    from app.core.blacklist import get_blocked_user_ids

    user_id = str(uuid.uuid4())
    blocked_uid = uuid.uuid4()

    redis = AsyncMock()
    redis.smembers = AsyncMock(return_value=set())
    mock_pipe = AsyncMock()
    redis.pipeline = MagicMock(return_value=mock_pipe)

    # Simulate DB returning one block row
    mock_conn.fetch = AsyncMock(
        return_value=[{"blocker_id": uuid.UUID(user_id), "blocked_id": blocked_uid}]
    )

    result = await get_blocked_user_ids(redis, user_id, pool=mock_pool)

    assert result == {str(blocked_uid)}
    mock_conn.fetch.assert_called_once()


@pytest.mark.anyio
async def test_get_blocked_user_ids_rewarms_cache_after_db_fallback(mock_pool, mock_conn):
    """Cache should be re-warmed from DB results via Redis pipeline."""
    from app.core.blacklist import get_blocked_user_ids

    user_id = str(uuid.uuid4())
    blocked_uid = uuid.uuid4()

    redis = AsyncMock()
    redis.smembers = AsyncMock(return_value=set())
    mock_pipe = AsyncMock()
    redis.pipeline = MagicMock(return_value=mock_pipe)

    mock_conn.fetch = AsyncMock(
        return_value=[{"blocker_id": uuid.UUID(user_id), "blocked_id": blocked_uid}]
    )

    await get_blocked_user_ids(redis, user_id, pool=mock_pool)

    # Verify pipeline was used to re-warm cache
    redis.pipeline.assert_called_once()
    mock_pipe.sadd.assert_called_once_with(f"block:set:{user_id}", str(blocked_uid))
    mock_pipe.expire.assert_called_once_with(f"block:set:{user_id}", 3600)
    mock_pipe.execute.assert_called_once()


@pytest.mark.anyio
async def test_get_blocked_user_ids_returns_empty_without_pool():
    """get_blocked_user_ids should return empty set on Redis miss when no pool."""
    from app.core.blacklist import get_blocked_user_ids

    redis = AsyncMock()
    redis.smembers = AsyncMock(return_value=set())

    result = await get_blocked_user_ids(redis, str(uuid.uuid4()))

    assert result == set()


@pytest.mark.anyio
async def test_get_blocked_user_ids_handles_db_error_gracefully(mock_pool, mock_conn):
    """get_blocked_user_ids should return empty set when DB fallback fails."""
    from app.core.blacklist import get_blocked_user_ids

    redis = AsyncMock()
    redis.smembers = AsyncMock(return_value=set())

    mock_conn.fetch = AsyncMock(side_effect=Exception("DB connection failed"))

    result = await get_blocked_user_ids(redis, str(uuid.uuid4()), pool=mock_pool)

    assert result == set()


@pytest.mark.anyio
async def test_get_blocked_user_ids_bilateral_block(mock_pool, mock_conn):
    """DB fallback should correctly handle when user is the blocked_id (not blocker)."""
    from app.core.blacklist import get_blocked_user_ids

    user_id = str(uuid.uuid4())
    blocker_uid = uuid.uuid4()

    redis = AsyncMock()
    redis.smembers = AsyncMock(return_value=set())
    mock_pipe = AsyncMock()
    redis.pipeline = MagicMock(return_value=mock_pipe)

    # User is the blocked party, not the blocker
    mock_conn.fetch = AsyncMock(
        return_value=[{"blocker_id": blocker_uid, "blocked_id": uuid.UUID(user_id)}]
    )

    result = await get_blocked_user_ids(redis, user_id, pool=mock_pool)

    assert result == {str(blocker_uid)}


# ── H1: accept_friend_request emits TWO friend.accepted events ────


_REPO = "app.repositories.social_repo"


def _make_friendship(requester_id=None, addressee_id=None, status="PENDING", friendship_id=None):
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)
    return {
        "id": friendship_id or uuid.uuid4(),
        "requester_id": requester_id or uuid.uuid4(),
        "addressee_id": addressee_id or uuid.uuid4(),
        "status": status,
        "created_at": now,
        "updated_at": now,
    }


class TestAcceptFriendRequestEmitsBothParties:
    """H1: accept_friend_request must emit friend.accepted
    for BOTH the requester and the accepter."""

    @patch(f"{_REPO}.insert_follow", new_callable=AsyncMock, return_value={})
    @patch(f"{_REPO}.is_following", new_callable=AsyncMock, return_value=False)
    @patch(f"{_REPO}.accept_friendship", new_callable=AsyncMock)
    @patch(f"{_REPO}.find_friendship_by_id_for_update", new_callable=AsyncMock)
    @patch("app.services.social.emit", new_callable=AsyncMock)
    @pytest.mark.anyio
    async def test_emits_two_friend_accepted_events(
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

        accepter_id = uuid.uuid4()
        requester_id = uuid.uuid4()
        friendship_id = uuid.uuid4()
        friendship = _make_friendship(requester_id, accepter_id, "PENDING", friendship_id)
        mock_find.return_value = friendship
        mock_accept.return_value = {**friendship, "status": "ACCEPTED"}

        await accept_friend_request(mock_pool, friendship_id, accepter_id)

        # Must emit exactly 2 events
        assert mock_emit.call_count == 2

        # First emit: notify the requester
        first = mock_emit.call_args_list[0]
        assert first.args[0] == "friend.accepted"
        assert first.kwargs["user_id"] == str(requester_id)
        assert first.kwargs["friend_id"] == str(accepter_id)
        assert first.kwargs["friendship_id"] == str(friendship_id)

        # Second emit: notify the accepter
        second = mock_emit.call_args_list[1]
        assert second.args[0] == "friend.accepted"
        assert second.kwargs["user_id"] == str(accepter_id)
        assert second.kwargs["friend_id"] == str(requester_id)
        assert second.kwargs["friendship_id"] == str(friendship_id)

    @patch(f"{_REPO}.insert_follow", new_callable=AsyncMock, return_value={})
    @patch(f"{_REPO}.is_following", new_callable=AsyncMock, return_value=False)
    @patch(f"{_REPO}.accept_friendship", new_callable=AsyncMock)
    @patch(f"{_REPO}.find_friendship_by_id_for_update", new_callable=AsyncMock)
    @patch("app.services.social.emit", new_callable=AsyncMock)
    @pytest.mark.anyio
    async def test_both_emits_use_same_friendship_id(
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

        accepter_id = uuid.uuid4()
        requester_id = uuid.uuid4()
        friendship_id = uuid.uuid4()
        friendship = _make_friendship(requester_id, accepter_id, "PENDING", friendship_id)
        mock_find.return_value = friendship
        mock_accept.return_value = {**friendship, "status": "ACCEPTED"}

        await accept_friend_request(mock_pool, friendship_id, accepter_id)

        # Both events reference the same friendship_id
        for call in mock_emit.call_args_list:
            assert call.kwargs["friendship_id"] == str(friendship_id)
