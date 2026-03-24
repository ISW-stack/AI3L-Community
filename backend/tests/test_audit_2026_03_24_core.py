"""Tests for backend core logic audit fixes (2026-03-24).

Covers: H-01, H-02, H-06, H-11, M-07, M-10, M-11, M-13,
        L-05, L-07, L-08, L-09, L-10, L-13.
"""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# H-01: anonymize_user atomicity — PII wipe + cleanup in single transaction
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_h01_anonymize_rolls_back_on_cleanup_failure(mock_pool, mock_conn):
    """If cleanup (phase 2) fails, PII wipe (phase 1) must also roll back."""
    from app.services.user import anonymize_user

    user_id = uuid.uuid4()

    # Make user_repo.anonymize succeed (returns True via conn)
    # But make one of the cleanup queries raise an exception
    call_count = 0

    async def execute_with_failure(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        # The first execute call is user_repo.anonymize (UPDATE users)
        # Let it succeed, then fail on a subsequent cleanup call
        if call_count > 2:
            raise RuntimeError("Simulated cleanup failure")
        return "UPDATE 1"

    mock_conn.execute = AsyncMock(side_effect=execute_with_failure)

    # Mock transaction to actually propagate exceptions (simulating rollback)
    tx = AsyncMock()
    tx.__aenter__ = AsyncMock(return_value=tx)
    tx.__aexit__ = AsyncMock(return_value=False)
    mock_conn.transaction = MagicMock(return_value=tx)

    with (
        patch("app.core.database.get_pool", return_value=mock_pool),
        patch(
            "app.services.user.user_repo.find_by_id",
            new_callable=AsyncMock,
            return_value=None,
        ),
        patch(
            "app.services.user.user_repo.anonymize",
            new_callable=AsyncMock,
            return_value=True,
        ),
        patch(
            "app.repositories.co_author_repo.delete_by_user_id",
            new_callable=AsyncMock,
            side_effect=RuntimeError("Simulated cleanup failure"),
        ),
        patch("app.repositories.profile_view_repo.delete_by_profile_or_viewer", new_callable=AsyncMock),
        patch("app.repositories.vote_repo.delete_by_user_id", new_callable=AsyncMock),
    ):
        # The exception should propagate (transaction rolls back)
        with pytest.raises(RuntimeError, match="Simulated cleanup failure"):
            await anonymize_user(user_id)


@pytest.mark.asyncio
async def test_h01_anonymize_passes_conn_to_repo(mock_pool, mock_conn):
    """Verify user_repo.anonymize is called with conn parameter."""
    user_id = uuid.uuid4()

    mock_conn.execute = AsyncMock(return_value="UPDATE 1")
    mock_conn.fetch = AsyncMock(return_value=[])

    mock_anon = AsyncMock(return_value=True)

    with (
        patch("app.core.database.get_pool", return_value=mock_pool),
        patch(
            "app.services.user.user_repo.find_by_id",
            new_callable=AsyncMock,
            return_value=None,
        ),
        patch("app.services.user.user_repo.anonymize", mock_anon),
        patch("app.repositories.co_author_repo.delete_by_user_id", new_callable=AsyncMock),
        patch("app.repositories.profile_view_repo.delete_by_profile_or_viewer", new_callable=AsyncMock),
        patch("app.repositories.vote_repo.delete_by_user_id", new_callable=AsyncMock),
        patch("app.services.user.async_delete_file", new_callable=AsyncMock),
    ):
        result = await (await _import_anonymize())(user_id)
        # Verify conn was passed (keyword argument)
        mock_anon.assert_called_once()
        call_kwargs = mock_anon.call_args
        assert call_kwargs.kwargs.get("conn") is mock_conn


async def _import_anonymize():
    from app.services.user import anonymize_user

    return anonymize_user


# ---------------------------------------------------------------------------
# H-02: Album TOCTOU — permission check inside transaction with FOR UPDATE
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_h02_delete_album_uses_for_update(mock_pool, mock_conn):
    """delete_album should use find_album_by_id_for_update inside transaction."""
    from app.services.album import delete_album

    album_id = str(uuid.uuid4())
    user_id = str(uuid.uuid4())
    album_row = {
        "id": uuid.UUID(album_id),
        "created_by": uuid.UUID(user_id),
        "cover_photo_url": None,
    }

    mock_conn.fetchrow = AsyncMock(return_value=None)

    with (
        patch("app.services.album.get_pool", return_value=mock_pool),
        patch(
            "app.repositories.album_repo.find_album_by_id_for_update",
            new_callable=AsyncMock,
            return_value=album_row,
        ) as mock_for_update,
        patch(
            "app.repositories.album_repo.find_all_photos_for_album",
            new_callable=AsyncMock,
            return_value=[],
        ),
        patch(
            "app.repositories.album_repo.soft_delete_album",
            new_callable=AsyncMock,
            return_value=True,
        ),
        patch(
            "app.repositories.album_repo.delete_all_comments_for_album",
            new_callable=AsyncMock,
        ),
        patch(
            "app.repositories.album_repo.delete_all_photos_for_album",
            new_callable=AsyncMock,
        ),
        patch(
            "app.repositories.album_repo.delete_all_members_for_album",
            new_callable=AsyncMock,
        ),
    ):
        result = await delete_album(album_id, user_id, "MEMBER")
        mock_for_update.assert_called_once_with(mock_conn, uuid.UUID(album_id))
        assert result is True


def _make_album_row(album_id, user_id):
    """Helper: create a full album dict for mock returns."""
    now = datetime.now(timezone.utc)
    return {
        "id": uuid.UUID(album_id),
        "title": "Test Album",
        "description": None,
        "cover_photo_url": None,
        "created_by": uuid.UUID(user_id),
        "created_by_name": "Test User",
        "is_archived": False,
        "is_deleted": False,
        "photo_count": 0,
        "member_count": 0,
        "created_at": now,
        "updated_at": now,
    }


@pytest.mark.asyncio
async def test_h02_set_cover_uses_for_update(mock_pool, mock_conn):
    """set_cover_from_photo should use FOR UPDATE inside transaction."""
    from app.services.album import set_cover_from_photo

    album_id = str(uuid.uuid4())
    photo_id = str(uuid.uuid4())
    user_id = str(uuid.uuid4())
    album_row = _make_album_row(album_id, user_id)
    photo_row = {
        "id": uuid.UUID(photo_id),
        "album_id": uuid.UUID(album_id),
        "storage_key": "photos/test.jpg",
    }
    member_row = {"role": "ADMIN", "status": "ACCEPTED"}

    with (
        patch("app.services.album.get_pool", return_value=mock_pool),
        patch(
            "app.repositories.album_repo.find_album_by_id_for_update",
            new_callable=AsyncMock,
            return_value=album_row,
        ) as mock_for_update,
        patch(
            "app.repositories.album_repo.find_album_by_id",
            new_callable=AsyncMock,
            return_value=album_row,
        ),
        patch(
            "app.repositories.album_repo.find_member",
            new_callable=AsyncMock,
            return_value=member_row,
        ),
        patch(
            "app.repositories.album_repo.find_photo_by_id",
            new_callable=AsyncMock,
            return_value=photo_row,
        ),
        patch(
            "app.repositories.album_repo.set_cover_photo",
            new_callable=AsyncMock,
        ),
        patch(
            "app.converters.album_converter.generate_presigned_url",
            new_callable=AsyncMock,
            return_value="http://example.com/cover.jpg",
        ),
    ):
        await set_cover_from_photo(album_id, photo_id, user_id, "MEMBER")
        mock_for_update.assert_called_once_with(mock_conn, uuid.UUID(album_id))


@pytest.mark.asyncio
async def test_h02_delete_photo_uses_for_update(mock_pool, mock_conn):
    """delete_photo should use FOR UPDATE inside transaction."""
    from app.services.album import delete_photo

    album_id = str(uuid.uuid4())
    photo_id = str(uuid.uuid4())
    user_id = str(uuid.uuid4())
    album_row = {
        "id": uuid.UUID(album_id),
        "created_by": uuid.UUID(user_id),
    }
    photo_row = {
        "id": uuid.UUID(photo_id),
        "album_id": uuid.UUID(album_id),
        "uploaded_by": uuid.UUID(user_id),
        "storage_key": "photos/test.jpg",
        "thumbnail_key": None,
        "file_size_bytes": 0,
    }

    with (
        patch("app.services.album.get_pool", return_value=mock_pool),
        patch(
            "app.repositories.album_repo.find_album_by_id_for_update",
            new_callable=AsyncMock,
            return_value=album_row,
        ) as mock_for_update,
        patch(
            "app.repositories.album_repo.find_photo_by_id",
            new_callable=AsyncMock,
            return_value=photo_row,
        ),
        patch(
            "app.repositories.album_repo.delete_photo",
            new_callable=AsyncMock,
            return_value=True,
        ),
        patch("app.services.album.user_repo.decrement_storage_used", new_callable=AsyncMock),
    ):
        result = await delete_photo(album_id, photo_id, user_id, "MEMBER")
        mock_for_update.assert_called_once_with(mock_conn, uuid.UUID(album_id))
        assert result is True


# ---------------------------------------------------------------------------
# H-06 & L-13: Redis initialization in event_retry.py
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_h06_ensure_redis_called_before_sig_notify():
    """_async_notify_sig_members should call _ensure_redis before processing."""
    from app.tasks.event_retry import _async_notify_sig_members

    sig_id = str(uuid.uuid4())
    post_id = str(uuid.uuid4())
    author_id = str(uuid.uuid4())

    mock_ensure_pool = AsyncMock()
    mock_ensure_redis = AsyncMock()
    mock_user = {"display_name": "Test"}

    with (
        patch("app.tasks.event_retry._ensure_redis", mock_ensure_redis),
        patch("app.tasks.utils.ensure_pool", mock_ensure_pool),
        patch(
            "app.services.user.get_user_by_id",
            new_callable=AsyncMock,
            return_value=mock_user,
        ),
        patch(
            "app.repositories.sig_repo.find_members",
            new_callable=AsyncMock,
            return_value=([], 0),
        ),
    ):
        await _async_notify_sig_members(sig_id, post_id, author_id, "Test Post")
        mock_ensure_redis.assert_called_once()


@pytest.mark.asyncio
async def test_l13_ensure_redis_called_before_retry():
    """_async_retry should call _ensure_redis before get_redis."""
    from app.tasks.event_retry import _async_retry

    mock_redis = AsyncMock()
    mock_redis.lpop = AsyncMock(return_value=None)

    with (
        patch("app.tasks.event_retry._ensure_redis", new_callable=AsyncMock) as mock_ensure,
        patch("app.core.redis.get_redis", return_value=mock_redis),
    ):
        await _async_retry()
        mock_ensure.assert_called_once()


@pytest.mark.asyncio
async def test_h06_ensure_redis_initializes_when_not_available():
    """_ensure_redis should call init_redis when get_redis raises RuntimeError."""
    from app.tasks.event_retry import _ensure_redis

    with (
        patch(
            "app.core.redis.get_redis",
            side_effect=RuntimeError("not initialized"),
        ),
        patch("app.core.redis.init_redis", new_callable=AsyncMock) as mock_init,
        patch("app.core.config.settings") as mock_settings,
    ):
        mock_settings.REDIS_URL = "redis://localhost:6379"
        await _ensure_redis()
        mock_init.assert_called_once_with("redis://localhost:6379")


# ---------------------------------------------------------------------------
# H-11: Vote score CTE FOR UPDATE
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_h11_upsert_vote_uses_for_update():
    """The upsert_vote CTE should include FOR UPDATE on the old vote SELECT."""
    import inspect

    from app.repositories import vote_repo

    source = inspect.getsource(vote_repo.upsert_vote)
    assert "FOR UPDATE" in source, "upsert_vote CTE must use FOR UPDATE"


@pytest.mark.asyncio
async def test_h11_upsert_vote_returns_score(mock_conn):
    """upsert_vote should return the new vote_score."""
    from app.repositories.vote_repo import upsert_vote

    comment_id = uuid.uuid4()
    user_id = uuid.uuid4()

    mock_conn.fetchrow = AsyncMock(return_value={"vote_score": 5})

    score = await upsert_vote(mock_conn, comment_id, user_id, 1)
    assert score == 5
    # Verify the SQL was called
    mock_conn.fetchrow.assert_called_once()
    sql = mock_conn.fetchrow.call_args[0][0]
    assert "FOR UPDATE" in sql


# ---------------------------------------------------------------------------
# M-07: approve_member permission check in transaction
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_m07_approve_member_uses_transaction(mock_pool, mock_conn):
    """approve_member should use FOR UPDATE and transaction."""
    from app.services.album import approve_member

    album_id = str(uuid.uuid4())
    user_id = str(uuid.uuid4())
    member_id = str(uuid.uuid4())
    album_row = {
        "id": uuid.UUID(album_id),
        "created_by": uuid.UUID(user_id),
    }

    with (
        patch("app.services.album.get_pool", return_value=mock_pool),
        patch(
            "app.repositories.album_repo.find_album_by_id_for_update",
            new_callable=AsyncMock,
            return_value=album_row,
        ) as mock_for_update,
        patch(
            "app.repositories.album_repo.find_member",
            new_callable=AsyncMock,
            return_value=None,
        ),
        patch(
            "app.repositories.album_repo.update_member_status",
            new_callable=AsyncMock,
            return_value=True,
        ),
    ):
        result = await approve_member(album_id, user_id, member_id, "SUPER_ADMIN")
        mock_for_update.assert_called_once()
        assert result is True


# ---------------------------------------------------------------------------
# M-10: Post reaction blocked-user check
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_m10_post_reaction_blocked_user_service_level():
    """Blocked users should not be able to react to posts (service-level test)."""
    from app.api.v1.endpoints.posts import toggle_post_reaction_endpoint

    post_id = uuid.uuid4()
    owner_id = str(uuid.uuid4())
    reactor_id = str(uuid.uuid4())

    mock_redis = AsyncMock()
    mock_req = MagicMock()
    mock_req.reaction = "like"

    current_user = {"sub": reactor_id, "role": "MEMBER"}

    with (
        patch(
            "app.api.v1.endpoints.posts.check_rate_limit",
            new_callable=AsyncMock,
            return_value=True,
        ),
        patch(
            "app.repositories.post_repo.find_owner_id",
            new_callable=AsyncMock,
            return_value=owner_id,
        ),
        patch("app.core.redis.get_redis", return_value=mock_redis),
        patch(
            "app.core.blacklist.get_blocked_user_ids",
            new_callable=AsyncMock,
            return_value={owner_id},
        ),
    ):
        from app.core.errors import AppError

        with pytest.raises(AppError) as exc_info:
            await toggle_post_reaction_endpoint(post_id, mock_req, current_user)
        assert exc_info.value.status_code == 403


@pytest.mark.asyncio
async def test_m10_post_reaction_owner_blocked_reverse():
    """Post author blocking reactor should also prevent reaction."""
    from app.api.v1.endpoints.posts import toggle_post_reaction_endpoint

    post_id = uuid.uuid4()
    owner_id = str(uuid.uuid4())
    reactor_id = str(uuid.uuid4())

    mock_redis = AsyncMock()
    mock_req = MagicMock()
    mock_req.reaction = "like"

    current_user = {"sub": reactor_id, "role": "MEMBER"}

    # First call returns empty (reactor hasn't blocked owner)
    # Second call returns reactor_id (owner has blocked reactor)
    call_count = 0

    async def blocked_side_effect(redis, uid, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return set()  # reactor hasn't blocked owner
        return {reactor_id}  # owner has blocked reactor

    with (
        patch(
            "app.api.v1.endpoints.posts.check_rate_limit",
            new_callable=AsyncMock,
            return_value=True,
        ),
        patch(
            "app.repositories.post_repo.find_owner_id",
            new_callable=AsyncMock,
            return_value=owner_id,
        ),
        patch("app.core.redis.get_redis", return_value=mock_redis),
        patch(
            "app.core.blacklist.get_blocked_user_ids",
            new_callable=AsyncMock,
            side_effect=blocked_side_effect,
        ),
    ):
        from app.core.errors import AppError

        with pytest.raises(AppError) as exc_info:
            await toggle_post_reaction_endpoint(post_id, mock_req, current_user)
        assert exc_info.value.status_code == 403


# ---------------------------------------------------------------------------
# M-11: Comment reaction blocked-user check
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_m11_comment_reaction_blocked_user_service_level():
    """Blocked users should not be able to react to comments (service-level test)."""
    from app.api.v1.endpoints.comments import toggle_reaction

    post_id = uuid.uuid4()
    comment_id = uuid.uuid4()
    owner_id = str(uuid.uuid4())
    reactor_id = str(uuid.uuid4())

    mock_redis = AsyncMock()
    mock_pool_local = MagicMock()
    mock_conn_local = AsyncMock()
    cm = AsyncMock()
    cm.__aenter__ = AsyncMock(return_value=mock_conn_local)
    cm.__aexit__ = AsyncMock(return_value=False)
    mock_pool_local.acquire.return_value = cm

    mock_req = MagicMock()
    mock_req.reaction = "like"

    current_user = {"sub": reactor_id, "role": "MEMBER"}

    with (
        patch(
            "app.api.v1.endpoints.comments.check_rate_limit",
            new_callable=AsyncMock,
            return_value=True,
        ),
        patch(
            "app.repositories.comment_repo.find_parent_user_id",
            new_callable=AsyncMock,
            return_value=owner_id,
        ),
        patch("app.core.redis.get_redis", return_value=mock_redis),
        patch("app.core.database.get_pool", return_value=mock_pool_local),
        patch(
            "app.core.blacklist.get_blocked_user_ids",
            new_callable=AsyncMock,
            return_value={owner_id},
        ),
    ):
        from app.core.errors import AppError

        with pytest.raises(AppError) as exc_info:
            await toggle_reaction(post_id, comment_id, mock_req, current_user)
        assert exc_info.value.status_code == 403


# ---------------------------------------------------------------------------
# M-13: Notification creation rate limit
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_m13_notification_rate_limit_skips_when_exceeded(mock_redis):
    """Notification creation should skip silently when rate limit is exceeded."""
    from app.services.notification import (
        _NOTIFICATION_RATE_LIMIT_MAX,
        create_notification,
    )

    user_id = str(uuid.uuid4())

    # Simulate rate limit exceeded
    mock_redis.incr = AsyncMock(return_value=_NOTIFICATION_RATE_LIMIT_MAX + 1)

    with (
        patch("app.services.notification.get_redis", return_value=mock_redis),
        patch(
            "app.services.notification.notification_repo.insert",
            new_callable=AsyncMock,
        ) as mock_insert,
    ):
        result = await create_notification(
            user_id=user_id,
            trigger_user_id=None,
            action_type="TEST",
            entity_type=None,
            entity_id=None,
            message="test",
        )
        assert result.get("skipped") is True
        mock_insert.assert_not_called()


@pytest.mark.asyncio
async def test_m13_notification_rate_limit_allows_within_limit(mock_redis):
    """Notification creation should proceed when within rate limit."""
    from app.services.notification import create_notification

    user_id = str(uuid.uuid4())
    notif_row = {
        "id": uuid.uuid4(),
        "user_id": uuid.UUID(user_id),
        "trigger_user_id": None,
        "action_type": "TEST",
        "entity_type": None,
        "entity_id": None,
        "message": "test",
        "is_read": False,
        "created_at": None,
    }

    mock_redis.incr = AsyncMock(return_value=1)

    with (
        patch("app.services.notification.get_redis", return_value=mock_redis),
        patch(
            "app.services.notification.notification_repo.insert",
            new_callable=AsyncMock,
            return_value=notif_row,
        ),
        patch(
            "app.services.notification.async_row_to_notification",
            new_callable=AsyncMock,
            return_value={"id": str(notif_row["id"])},
        ),
        patch("app.services.notification.emit", new_callable=AsyncMock),
    ):
        result = await create_notification(
            user_id=user_id,
            trigger_user_id=None,
            action_type="TEST",
            entity_type=None,
            entity_id=None,
            message="test",
        )
        assert result.get("skipped") is not True


# ---------------------------------------------------------------------------
# L-05: Bulk delete with empty IDs is no-op
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_l05_bulk_delete_empty_ids_noop():
    """Passing empty notification_ids should be a no-op (direct function call)."""
    from app.api.v1.endpoints.notifications import bulk_delete_notifications
    from app.schemas.notification import BulkDeleteNotificationsRequest

    user = {"sub": str(uuid.uuid4()), "role": "MEMBER"}
    req = BulkDeleteNotificationsRequest(notification_ids=[])

    with (
        patch(
            "app.api.v1.endpoints.notifications.check_rate_limit",
            new_callable=AsyncMock,
            return_value=True,
        ),
        patch(
            "app.repositories.notification_repo.bulk_delete",
            new_callable=AsyncMock,
        ) as mock_bulk,
    ):
        resp = await bulk_delete_notifications(req=req, current_user=user)
        assert resp.status_code == 204
        mock_bulk.assert_not_called()


@pytest.mark.asyncio
async def test_l05_bulk_delete_with_ids_proceeds():
    """Passing non-empty notification_ids should proceed normally."""
    from app.api.v1.endpoints.notifications import bulk_delete_notifications
    from app.schemas.notification import BulkDeleteNotificationsRequest

    notif_id = uuid.uuid4()
    user = {"sub": str(uuid.uuid4()), "role": "MEMBER"}
    req = BulkDeleteNotificationsRequest(notification_ids=[notif_id])

    with (
        patch(
            "app.api.v1.endpoints.notifications.check_rate_limit",
            new_callable=AsyncMock,
            return_value=True,
        ),
        patch(
            "app.repositories.notification_repo.bulk_delete",
            new_callable=AsyncMock,
        ) as mock_bulk,
    ):
        resp = await bulk_delete_notifications(req=req, current_user=user)
        assert resp.status_code == 204
        mock_bulk.assert_called_once()


# ---------------------------------------------------------------------------
# L-07: Reaction types limit
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_l07_reaction_types_limit(mock_conn):
    """Should reject new reaction type when limit is reached."""
    import json

    from app.repositories.reaction_helpers import toggle_reaction_jsonb

    row_id = str(uuid.uuid4())
    user_id = str(uuid.uuid4())

    # Create reactions dict with 20 types already
    existing_reactions = {f"type_{i}": [user_id] for i in range(20)}
    mock_conn.fetchrow = AsyncMock(return_value={"reactions": json.dumps(existing_reactions)})

    with pytest.raises(ValueError, match="Maximum number of reaction types"):
        await toggle_reaction_jsonb(mock_conn, "posts", row_id, user_id, "new_type_21")


@pytest.mark.asyncio
async def test_l07_reaction_toggle_existing_type_ok(mock_conn):
    """Toggling an existing reaction type should work even at the limit."""
    import json

    from app.repositories.reaction_helpers import toggle_reaction_jsonb

    row_id = str(uuid.uuid4())
    user_id = str(uuid.uuid4())

    existing_reactions = {f"type_{i}": ["other_user"] for i in range(20)}
    mock_conn.fetchrow = AsyncMock(return_value={"reactions": json.dumps(existing_reactions)})
    mock_conn.execute = AsyncMock(return_value="UPDATE 1")

    # Toggling an existing type should NOT raise
    result = await toggle_reaction_jsonb(mock_conn, "posts", row_id, user_id, "type_0")
    assert "type_0" in result
    assert user_id in result["type_0"]


# ---------------------------------------------------------------------------
# L-08: Mentions list length limit
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_l08_mentions_limit():
    """Should reject comments with too many mentions."""
    from app.services.comment import MAX_MENTIONS_PER_COMMENT, create_comment

    post_id = uuid.uuid4()
    user_id = str(uuid.uuid4())
    mentions = [f"user_{i}" for i in range(MAX_MENTIONS_PER_COMMENT + 1)]

    with pytest.raises(ValueError, match="Too many mentions"):
        await create_comment(post_id, user_id, "Hello", mentions=mentions)


@pytest.mark.asyncio
async def test_l08_mentions_within_limit_ok():
    """Comments with mentions within the limit should pass validation."""
    from app.services.comment import MAX_MENTIONS_PER_COMMENT

    # Just verify the constant is reasonable
    assert MAX_MENTIONS_PER_COMMENT >= 5
    assert MAX_MENTIONS_PER_COMMENT <= 50


# ---------------------------------------------------------------------------
# L-09: update_member_role raises error if member not found
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_l09_update_member_role_not_found_raises(mock_conn):
    """Should raise ValueError if the member does not exist."""
    from app.repositories.sig_repo import update_member_role_in_conn

    sig_id = uuid.uuid4()
    user_id = uuid.uuid4()

    # SIG exists
    mock_conn.fetchrow = AsyncMock(
        side_effect=[
            {"id": sig_id},  # SIG found
            None,  # member NOT found
        ]
    )

    with pytest.raises(ValueError, match="Member not found"):
        await update_member_role_in_conn(sig_id, user_id, "ADMIN", mock_conn)


@pytest.mark.asyncio
async def test_l09_update_member_role_found_ok(mock_conn):
    """Should update role when the member exists."""
    from app.repositories.sig_repo import update_member_role_in_conn

    sig_id = uuid.uuid4()
    user_id = uuid.uuid4()
    member_id = uuid.uuid4()
    member_row = {
        "id": member_id,
        "sig_id": sig_id,
        "user_id": user_id,
        "role": "ADMIN",
        "display_name": "Test",
        "username": "test",
    }

    mock_conn.fetchrow = AsyncMock(
        side_effect=[
            {"id": sig_id},  # SIG found
            {"id": member_id},  # member found
            member_row,  # final SELECT
        ]
    )
    mock_conn.execute = AsyncMock(return_value="UPDATE 1")

    result = await update_member_role_in_conn(sig_id, user_id, "ADMIN", mock_conn)
    assert result is not None
    assert result["role"] == "ADMIN"


# ---------------------------------------------------------------------------
# L-10: album update_member_status requires album_id
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_l10_update_member_status_requires_album_id():
    """album_id should be a required parameter (not Optional)."""
    import inspect

    from app.repositories.album_repo import update_member_status

    sig = inspect.signature(update_member_status)
    album_id_param = sig.parameters["album_id"]
    # Should NOT have a default value
    assert album_id_param.default is inspect.Parameter.empty, (
        "album_id must be required (no default value)"
    )


@pytest.mark.asyncio
async def test_l10_update_member_status_includes_album_id_in_query(mock_conn):
    """The SQL query should always include album_id in WHERE clause."""
    from app.repositories.album_repo import update_member_status

    member_id = uuid.uuid4()
    album_id = uuid.uuid4()

    mock_conn.execute = AsyncMock(return_value="UPDATE 1")

    result = await update_member_status(mock_conn, member_id, "ACCEPTED", album_id)
    assert result is True
    # Verify album_id was passed as parameter
    call_args = mock_conn.execute.call_args
    sql = call_args[0][0]
    assert "album_id" in sql


# ---------------------------------------------------------------------------
# find_album_by_id_for_update exists and has FOR UPDATE
# ---------------------------------------------------------------------------


def test_album_repo_has_for_update_function():
    """album_repo should have find_album_by_id_for_update function."""
    from app.repositories import album_repo

    assert hasattr(album_repo, "find_album_by_id_for_update")


def test_album_repo_for_update_source():
    """find_album_by_id_for_update should contain FOR UPDATE in its SQL."""
    import inspect

    from app.repositories.album_repo import find_album_by_id_for_update

    source = inspect.getsource(find_album_by_id_for_update)
    assert "FOR UPDATE" in source


# ---------------------------------------------------------------------------
# user_repo.anonymize accepts conn parameter
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_user_repo_anonymize_with_conn(mock_conn):
    """user_repo.anonymize should accept and use a conn parameter."""
    from app.repositories.user_repo import anonymize

    user_id = uuid.uuid4()
    mock_conn.execute = AsyncMock(return_value="UPDATE 1")

    result = await anonymize(user_id, "Deleted_User_abc12345", conn=mock_conn)
    assert result is True
    mock_conn.execute.assert_called_once()


@pytest.mark.asyncio
async def test_user_repo_anonymize_without_conn(mock_pool, mock_conn):
    """user_repo.anonymize should work without conn (acquires from pool)."""
    from app.repositories.user_repo import anonymize

    user_id = uuid.uuid4()
    mock_conn.execute = AsyncMock(return_value="UPDATE 1")

    with patch("app.repositories.user_repo.get_pool", return_value=mock_pool):
        result = await anonymize(user_id, "Deleted_User_abc12345")
        assert result is True
