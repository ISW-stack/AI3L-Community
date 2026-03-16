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
        )

        mock_create.assert_called_once_with(
            user_id=requester_id,
            trigger_user_id=friend_id,
            action_type="FRIEND_ACCEPTED",
            entity_type="friendship",
            entity_id=None,
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
        )

        mock_create.assert_not_called()


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
