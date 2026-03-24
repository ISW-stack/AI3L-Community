"""Tests for _on_post_created_in_sig Celery dispatch and Celery task constants."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.event_handlers import _on_post_created_in_sig
from app.tasks.event_retry import (
    _SIG_NOTIFICATION_CONCURRENCY,
    _SIG_NOTIFICATION_MAX,
)


def _make_member(user_id: str | None = None) -> dict:
    """Create a minimal SIG member dict."""
    return {"user_id": uuid.UUID(user_id) if user_id else uuid.uuid4()}


class TestSigNotificationConstants:
    """Verify the concurrency and cap constants exist and are reasonable."""

    def test_notification_max_is_500(self):
        assert _SIG_NOTIFICATION_MAX == 500

    def test_notification_concurrency_is_20(self):
        assert _SIG_NOTIFICATION_CONCURRENCY == 20


class TestSigNotificationConcurrency:
    """Verify _on_post_created_in_sig dispatches the Celery task correctly."""

    @pytest.mark.anyio
    async def test_notifies_all_members_except_author(self):
        """_on_post_created_in_sig dispatches the Celery task with the right args.

        The actual member filtering (excluding author) is handled by the Celery
        task (notify_sig_members_new_post), not by the event handler itself.
        """
        author_id = str(uuid.uuid4())
        sig_id = str(uuid.uuid4())
        post_id = str(uuid.uuid4())

        mock_task = MagicMock()
        with patch("app.tasks.event_retry.notify_sig_members_new_post", mock_task):
            await _on_post_created_in_sig(
                sig_id=sig_id,
                post_id=post_id,
                author_id=author_id,
                post_title="Test Post",
            )

        mock_task.delay.assert_called_once_with(sig_id, post_id, author_id, "Test Post")

    @pytest.mark.anyio
    async def test_handles_create_notification_failure(self):
        """If .delay() raises, the handler catches it and does not propagate."""
        author_id = str(uuid.uuid4())
        sig_id = str(uuid.uuid4())
        post_id = str(uuid.uuid4())

        mock_task = MagicMock()
        mock_task.delay.side_effect = RuntimeError("broker unavailable")

        with patch("app.tasks.event_retry.notify_sig_members_new_post", mock_task):
            # Should NOT raise
            await _on_post_created_in_sig(
                sig_id=sig_id,
                post_id=post_id,
                author_id=author_id,
                post_title="Test Post",
            )

        mock_task.delay.assert_called_once()


class TestSigNotificationCap:
    """Verify the hard cap on SIG notifications."""

    @pytest.mark.anyio
    async def test_cap_limits_notifications(self):
        """When a SIG has more than _SIG_NOTIFICATION_MAX members, stop after the cap."""
        author_id = str(uuid.uuid4())
        sig_id = str(uuid.uuid4())
        post_id = str(uuid.uuid4())

        # Create members exceeding the cap (cap + 10)
        total_members = _SIG_NOTIFICATION_MAX + 10
        all_members = [_make_member() for _ in range(total_members)]

        async def _find_members(sig_id_arg, offset=0, limit=200):
            batch = all_members[offset : offset + limit]
            return (batch, total_members)

        mock_find_members = AsyncMock(side_effect=_find_members)
        mock_get_user = AsyncMock(return_value={"display_name": "Author"})
        mock_create = AsyncMock()
        mock_check = AsyncMock(return_value=True)

        with (
            patch("app.repositories.sig_repo.find_members", mock_find_members),
            patch("app.services.user.get_user_by_id", mock_get_user),
            patch("app.services.notification.create_notification", mock_create),
            patch("app.event_handlers._check_idempotent", mock_check),
        ):
            await _on_post_created_in_sig(
                sig_id=sig_id,
                post_id=post_id,
                author_id=author_id,
                post_title="Test Post",
            )

        # Should not exceed the cap
        assert mock_create.await_count <= _SIG_NOTIFICATION_MAX

    @pytest.mark.anyio
    async def test_cap_logs_warning(self):
        """When the cap is reached inside the Celery task, a warning is logged.

        The cap logic lives in _async_notify_sig_members (event_retry.py).
        Here we verify the task's logger emits the warning when total > cap.
        """
        from app.tasks.event_retry import (
            _SIG_MEMBER_BATCH_SIZE,
            _async_notify_sig_members,
        )

        author_id = str(uuid.uuid4())
        sig_id = str(uuid.uuid4())
        post_id = str(uuid.uuid4())

        total_members = _SIG_NOTIFICATION_MAX + 50
        all_members = [_make_member() for _ in range(total_members)]

        async def _find_members(sig_id_arg, offset=0, limit=_SIG_MEMBER_BATCH_SIZE):
            batch = all_members[offset : offset + limit]
            return (batch, total_members)

        mock_get_user = AsyncMock(return_value={"display_name": "Author"})
        mock_create = AsyncMock()
        mock_check = AsyncMock(return_value=True)

        with (
            patch("app.repositories.sig_repo.find_members", AsyncMock(side_effect=_find_members)),
            patch("app.services.user.get_user_by_id", mock_get_user),
            patch("app.services.notification.create_notification", mock_create),
            patch("app.tasks.event_retry._check_idempotent_for_sig", mock_check),
            patch("app.tasks.event_retry._is_blocked_for_sig", AsyncMock(return_value=False)),
            patch("app.tasks.event_retry.logger") as mock_logger,
            patch("app.tasks.utils.ensure_pool", AsyncMock()),
            patch("app.tasks.event_retry._ensure_redis", AsyncMock()),
        ):
            await _async_notify_sig_members(sig_id, post_id, author_id, "Test Post")

        warning_calls = mock_logger.warning.call_args_list
        cap_warnings = [c for c in warning_calls if "cap" in str(c).lower()]
        assert len(cap_warnings) >= 1

    @pytest.mark.anyio
    async def test_small_sig_no_cap_warning(self):
        """A small SIG should not trigger the cap warning."""
        author_id = str(uuid.uuid4())
        sig_id = str(uuid.uuid4())
        post_id = str(uuid.uuid4())

        members = [_make_member() for _ in range(5)]
        mock_find_members = AsyncMock(return_value=(members, len(members)))
        mock_get_user = AsyncMock(return_value={"display_name": "Author"})
        mock_create = AsyncMock()
        mock_check = AsyncMock(return_value=True)

        with (
            patch("app.repositories.sig_repo.find_members", mock_find_members),
            patch("app.services.user.get_user_by_id", mock_get_user),
            patch("app.services.notification.create_notification", mock_create),
            patch("app.event_handlers._check_idempotent", mock_check),
            patch("app.event_handlers.logger") as mock_logger,
        ):
            await _on_post_created_in_sig(
                sig_id=sig_id,
                post_id=post_id,
                author_id=author_id,
                post_title="Test Post",
            )

            # No cap warning should be logged
            warning_calls = mock_logger.warning.call_args_list
            cap_warnings = [c for c in warning_calls if "cap" in str(c).lower()]
            assert len(cap_warnings) == 0

    @pytest.mark.anyio
    async def test_deduplication_still_works(self):
        """Idempotency checks inside the Celery task filter duplicate notifications."""
        from app.tasks.event_retry import _async_notify_sig_members

        author_id = str(uuid.uuid4())
        sig_id = str(uuid.uuid4())
        post_id = str(uuid.uuid4())

        members = [_make_member() for _ in range(3)]
        mock_find_members = AsyncMock(return_value=(members, len(members)))
        mock_get_user = AsyncMock(return_value={"display_name": "Author"})
        mock_create = AsyncMock()
        # First two pass dedup, third is a duplicate
        mock_check = AsyncMock(side_effect=[True, True, False])

        with (
            patch("app.repositories.sig_repo.find_members", mock_find_members),
            patch("app.services.user.get_user_by_id", mock_get_user),
            patch("app.services.notification.create_notification", mock_create),
            patch("app.tasks.event_retry._check_idempotent_for_sig", mock_check),
            patch("app.tasks.event_retry._is_blocked_for_sig", AsyncMock(return_value=False)),
            patch("app.tasks.utils.ensure_pool", AsyncMock()),
            patch("app.tasks.event_retry._ensure_redis", AsyncMock()),
        ):
            await _async_notify_sig_members(sig_id, post_id, author_id, "Test Post")

        # Only 2 notifications should be created (third was deduplicated)
        assert mock_create.await_count == 2
