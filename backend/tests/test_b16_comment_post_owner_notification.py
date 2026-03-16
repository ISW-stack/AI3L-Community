"""B16: Comment creation notifies the post author."""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestCommentEmitsPostOwner:
    """create_comment emits post_owner_id and post_id in the event."""

    @pytest.mark.anyio
    async def test_emit_includes_post_owner_id(self) -> None:
        """comment.created event should include post_owner_id for notifications."""
        post_id = uuid.uuid4()
        comment_id = uuid.uuid4()
        user_id = str(uuid.uuid4())
        post_owner_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)

        mock_row = {
            "id": comment_id,
            "post_id": post_id,
            "user_id": uuid.UUID(user_id),
            "parent_id": None,
            "content": "Hello",
            "mentions": None,
            "reactions": {},
            "created_at": now,
            "updated_at": now,
            "author_id": uuid.UUID(user_id),
            "author_username": "alice",
            "author_display_name": "Alice",
            "author_avatar_url": None,
        }

        mock_post = {"id": post_id, "allow_comments": True, "comment_count": 0}

        conn = AsyncMock()
        conn.fetchrow = AsyncMock(side_effect=[mock_post, mock_row])
        conn.execute = AsyncMock()

        tx = AsyncMock()
        tx.__aenter__ = AsyncMock(return_value=tx)
        tx.__aexit__ = AsyncMock(return_value=False)
        conn.transaction = MagicMock(return_value=tx)

        cm = AsyncMock()
        cm.__aenter__ = AsyncMock(return_value=conn)
        cm.__aexit__ = AsyncMock(return_value=False)

        mock_pool_obj = MagicMock()
        mock_pool_obj.acquire.return_value = cm

        emit_calls: list[tuple[str, dict]] = []

        async def mock_emit(event: str, **kwargs: object) -> None:
            emit_calls.append((event, kwargs))

        mock_redis = AsyncMock()
        mock_redis.smembers = AsyncMock(return_value=set())

        with (
            patch("app.services.comment.get_pool", return_value=mock_pool_obj),
            patch("app.services.comment.emit", side_effect=mock_emit),
            patch("app.converters.shared.resolve_avatar_url", return_value=None),
            patch(
                "app.repositories.post_repo.find_owner_id",
                new_callable=AsyncMock,
                return_value=post_owner_id,
            ),
            patch("app.services.comment.get_redis", return_value=mock_redis),
        ):
            from app.services.comment import create_comment

            await create_comment(
                post_id=post_id,
                user_id=user_id,
                content="Hello",
            )

        assert len(emit_calls) == 1
        event, kwargs = emit_calls[0]
        assert event == "comment.created"
        assert kwargs["post_owner_id"] == post_owner_id
        assert kwargs["post_id"] == str(post_id)

    @pytest.mark.anyio
    async def test_self_comment_has_same_owner_id(self) -> None:
        """When the commenter IS the post owner, post_owner_id is still emitted
        (the handler skips the notification)."""
        post_id = uuid.uuid4()
        comment_id = uuid.uuid4()
        user_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)

        mock_row = {
            "id": comment_id,
            "post_id": post_id,
            "user_id": uuid.UUID(user_id),
            "parent_id": None,
            "content": "Self comment",
            "mentions": None,
            "reactions": {},
            "created_at": now,
            "updated_at": now,
            "author_id": uuid.UUID(user_id),
            "author_username": "alice",
            "author_display_name": "Alice",
            "author_avatar_url": None,
        }

        mock_post = {"id": post_id, "allow_comments": True, "comment_count": 0}

        conn = AsyncMock()
        conn.fetchrow = AsyncMock(side_effect=[mock_post, mock_row])
        conn.execute = AsyncMock()

        tx = AsyncMock()
        tx.__aenter__ = AsyncMock(return_value=tx)
        tx.__aexit__ = AsyncMock(return_value=False)
        conn.transaction = MagicMock(return_value=tx)

        cm = AsyncMock()
        cm.__aenter__ = AsyncMock(return_value=conn)
        cm.__aexit__ = AsyncMock(return_value=False)

        mock_pool_obj = MagicMock()
        mock_pool_obj.acquire.return_value = cm

        emit_calls: list[tuple[str, dict]] = []

        async def mock_emit(event: str, **kwargs: object) -> None:
            emit_calls.append((event, kwargs))

        mock_redis = AsyncMock()
        mock_redis.smembers = AsyncMock(return_value=set())

        with (
            patch("app.services.comment.get_pool", return_value=mock_pool_obj),
            patch("app.services.comment.emit", side_effect=mock_emit),
            patch("app.converters.shared.resolve_avatar_url", return_value=None),
            patch(
                "app.repositories.post_repo.find_owner_id",
                new_callable=AsyncMock,
                return_value=user_id,  # Owner is same as commenter
            ),
            patch("app.services.comment.get_redis", return_value=mock_redis),
        ):
            from app.services.comment import create_comment

            await create_comment(
                post_id=post_id,
                user_id=user_id,
                content="Self comment",
            )

        assert len(emit_calls) == 1
        event, kwargs = emit_calls[0]
        assert kwargs["post_owner_id"] == user_id


class TestEventHandlerPostOwnerNotification:
    """_on_comment_created sends NEW_COMMENT notification to post owner."""

    @pytest.mark.anyio
    async def test_post_owner_receives_notification(self) -> None:
        """Post owner should receive a NEW_COMMENT notification."""
        from app.event_handlers import _on_comment_created

        user_id = str(uuid.uuid4())
        post_owner_id = str(uuid.uuid4())
        post_id = str(uuid.uuid4())

        mock_create = AsyncMock()
        mock_check = AsyncMock(return_value=True)

        with (
            patch("app.services.notification.create_notification", mock_create),
            patch("app.event_handlers._check_idempotent", mock_check),
            patch("app.event_handlers._is_blocked", new_callable=AsyncMock, return_value=False),
        ):
            await _on_comment_created(
                user_id=user_id,
                commenter_name="Alice",
                mention_targets=[],
                reply_target=None,
                post_owner_id=post_owner_id,
                post_id=post_id,
            )

        # Should have been called exactly once for the post owner
        assert mock_create.call_count == 1
        call_kwargs = mock_create.call_args.kwargs
        assert call_kwargs["user_id"] == post_owner_id
        assert call_kwargs["action_type"] == "NEW_COMMENT"
        assert call_kwargs["entity_type"] == "post"
        assert call_kwargs["entity_id"] == post_id
        assert "commented on your post" in call_kwargs["message"]

    @pytest.mark.anyio
    async def test_self_comment_skips_post_owner_notification(self) -> None:
        """Post owner commenting on their own post should NOT get a notification."""
        from app.event_handlers import _on_comment_created

        user_id = str(uuid.uuid4())
        post_id = str(uuid.uuid4())

        mock_create = AsyncMock()

        with (
            patch("app.services.notification.create_notification", mock_create),
            patch(
                "app.event_handlers._check_idempotent",
                new_callable=AsyncMock,
                return_value=True,
            ),
            patch("app.event_handlers._is_blocked", new_callable=AsyncMock, return_value=False),
        ):
            await _on_comment_created(
                user_id=user_id,
                commenter_name="Alice",
                mention_targets=[],
                reply_target=None,
                post_owner_id=user_id,  # same as commenter
                post_id=post_id,
            )

        mock_create.assert_not_called()

    @pytest.mark.anyio
    async def test_post_owner_not_double_notified_when_mentioned(self) -> None:
        """If post owner is also mentioned, they should NOT get a duplicate NEW_COMMENT."""
        from app.event_handlers import _on_comment_created

        user_id = str(uuid.uuid4())
        post_owner_id = str(uuid.uuid4())
        post_id = str(uuid.uuid4())

        mock_create = AsyncMock()
        mock_check = AsyncMock(return_value=True)

        with (
            patch("app.services.notification.create_notification", mock_create),
            patch("app.event_handlers._check_idempotent", mock_check),
            patch("app.event_handlers._is_blocked", new_callable=AsyncMock, return_value=False),
        ):
            await _on_comment_created(
                user_id=user_id,
                commenter_name="Alice",
                mention_targets=[(post_owner_id, post_id)],  # Owner is mentioned
                reply_target=None,
                post_owner_id=post_owner_id,
                post_id=post_id,
            )

        # Should get MENTION notification but NOT a separate NEW_COMMENT
        assert mock_create.call_count == 1
        call_kwargs = mock_create.call_args.kwargs
        assert call_kwargs["action_type"] == "MENTION"

    @pytest.mark.anyio
    async def test_post_owner_not_double_notified_when_reply_target(self) -> None:
        """If post owner is the reply target, they should NOT get a duplicate NEW_COMMENT."""
        from app.event_handlers import _on_comment_created

        user_id = str(uuid.uuid4())
        post_owner_id = str(uuid.uuid4())
        post_id = str(uuid.uuid4())

        mock_create = AsyncMock()
        mock_check = AsyncMock(return_value=True)

        with (
            patch("app.services.notification.create_notification", mock_create),
            patch("app.event_handlers._check_idempotent", mock_check),
            patch("app.event_handlers._is_blocked", new_callable=AsyncMock, return_value=False),
        ):
            await _on_comment_created(
                user_id=user_id,
                commenter_name="Alice",
                mention_targets=[],
                reply_target=(post_owner_id, post_id),  # Owner is reply target
                post_owner_id=post_owner_id,
                post_id=post_id,
            )

        # Should get REPLY notification but NOT a separate NEW_COMMENT
        assert mock_create.call_count == 1
        call_kwargs = mock_create.call_args.kwargs
        assert call_kwargs["action_type"] == "REPLY"

    @pytest.mark.anyio
    async def test_blocked_post_owner_skipped(self) -> None:
        """Post owner who has blocked the commenter should NOT get notification."""
        from app.event_handlers import _on_comment_created

        user_id = str(uuid.uuid4())
        post_owner_id = str(uuid.uuid4())
        post_id = str(uuid.uuid4())

        mock_create = AsyncMock()

        async def mock_is_blocked(target: str, source: str) -> bool:
            return target == post_owner_id

        with (
            patch("app.services.notification.create_notification", mock_create),
            patch(
                "app.event_handlers._check_idempotent",
                new_callable=AsyncMock,
                return_value=True,
            ),
            patch("app.event_handlers._is_blocked", side_effect=mock_is_blocked),
        ):
            await _on_comment_created(
                user_id=user_id,
                commenter_name="Alice",
                mention_targets=[],
                reply_target=None,
                post_owner_id=post_owner_id,
                post_id=post_id,
            )

        mock_create.assert_not_called()

    @pytest.mark.anyio
    async def test_no_post_owner_id_skips_notification(self) -> None:
        """When post_owner_id is None, no post-owner notification should be sent."""
        from app.event_handlers import _on_comment_created

        user_id = str(uuid.uuid4())
        mock_create = AsyncMock()

        with (
            patch("app.services.notification.create_notification", mock_create),
            patch(
                "app.event_handlers._check_idempotent",
                new_callable=AsyncMock,
                return_value=True,
            ),
            patch("app.event_handlers._is_blocked", new_callable=AsyncMock, return_value=False),
        ):
            await _on_comment_created(
                user_id=user_id,
                commenter_name="Alice",
                mention_targets=[],
                reply_target=None,
                post_owner_id=None,
                post_id=None,
            )

        mock_create.assert_not_called()
