"""B6: Comment MENTION and REPLY notifications use entity_type='post' with post_id.

The frontend navigates to /forum/{entity_id} for both 'post' and 'comment' entity types,
so entity_id must always be a post_id. Using entity_type='post' is semantically correct
since we link to the post page.
"""

import uuid
from unittest.mock import AsyncMock, patch

import pytest


class TestMentionNotificationEntityType:
    """MENTION notifications from comments should use entity_type='post'."""

    @pytest.mark.anyio
    async def test_mention_notification_has_entity_type_post(self) -> None:
        from app.event_handlers import _on_comment_created

        user_id = str(uuid.uuid4())
        target_uid = str(uuid.uuid4())
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
                mention_targets=[(target_uid, post_id)],
                reply_target=None,
                post_owner_id=None,
                post_id=None,
            )

        assert mock_create.call_count == 1
        call_kwargs = mock_create.call_args.kwargs
        assert call_kwargs["action_type"] == "MENTION"
        assert call_kwargs["entity_type"] == "post"
        assert call_kwargs["entity_id"] == post_id

    @pytest.mark.anyio
    async def test_mention_idempotency_uses_post_entity_type(self) -> None:
        """_check_idempotent should be called with entity_type='post' for mentions."""
        from app.event_handlers import _on_comment_created

        user_id = str(uuid.uuid4())
        target_uid = str(uuid.uuid4())
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
                mention_targets=[(target_uid, post_id)],
                reply_target=None,
                post_owner_id=None,
                post_id=None,
            )

        # Verify idempotency check uses "post" not "comment"
        mock_check.assert_called_once_with(target_uid, "post", post_id, "MENTION")


class TestReplyNotificationEntityType:
    """REPLY notifications from comments should use entity_type='post'."""

    @pytest.mark.anyio
    async def test_reply_notification_has_entity_type_post(self) -> None:
        from app.event_handlers import _on_comment_created

        user_id = str(uuid.uuid4())
        parent_user_id = str(uuid.uuid4())
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
                commenter_name="Bob",
                mention_targets=[],
                reply_target=(parent_user_id, post_id),
                post_owner_id=None,
                post_id=None,
            )

        assert mock_create.call_count == 1
        call_kwargs = mock_create.call_args.kwargs
        assert call_kwargs["action_type"] == "REPLY"
        assert call_kwargs["entity_type"] == "post"
        assert call_kwargs["entity_id"] == post_id

    @pytest.mark.anyio
    async def test_reply_idempotency_uses_post_entity_type(self) -> None:
        """_check_idempotent should be called with entity_type='post' for replies."""
        from app.event_handlers import _on_comment_created

        user_id = str(uuid.uuid4())
        parent_user_id = str(uuid.uuid4())
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
                commenter_name="Bob",
                mention_targets=[],
                reply_target=(parent_user_id, post_id),
                post_owner_id=None,
                post_id=None,
            )

        mock_check.assert_called_once_with(parent_user_id, "post", post_id, "REPLY")


class TestNewCommentNotificationUnchanged:
    """NEW_COMMENT notification for post owner should still use entity_type='post'."""

    @pytest.mark.anyio
    async def test_new_comment_still_uses_post_entity_type(self) -> None:
        from app.event_handlers import _on_comment_created

        user_id = str(uuid.uuid4())
        post_owner_id = str(uuid.uuid4())
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
                post_owner_id=post_owner_id,
                post_id=post_id,
            )

        assert mock_create.call_count == 1
        call_kwargs = mock_create.call_args.kwargs
        assert call_kwargs["action_type"] == "NEW_COMMENT"
        assert call_kwargs["entity_type"] == "post"
        assert call_kwargs["entity_id"] == post_id

    @pytest.mark.anyio
    async def test_all_three_notification_types_use_post_entity(self) -> None:
        """When mention + reply + post owner all fire, all use entity_type='post'."""
        from app.event_handlers import _on_comment_created

        user_id = str(uuid.uuid4())
        mention_uid = str(uuid.uuid4())
        reply_uid = str(uuid.uuid4())
        post_owner_id = str(uuid.uuid4())
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
                mention_targets=[(mention_uid, post_id)],
                reply_target=(reply_uid, post_id),
                post_owner_id=post_owner_id,
                post_id=post_id,
            )

        assert mock_create.call_count == 3
        for call in mock_create.call_args_list:
            assert call.kwargs["entity_type"] == "post"
            assert call.kwargs["entity_id"] == post_id
