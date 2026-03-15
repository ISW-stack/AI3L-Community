"""Tests for Bug #7: _on_post_created_in_sig concurrency and cap limits."""

import uuid
from unittest.mock import AsyncMock, patch

import pytest

from app.event_handlers import (
    _SIG_NOTIFICATION_CONCURRENCY,
    _SIG_NOTIFICATION_MAX,
    _on_post_created_in_sig,
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
    """Verify notifications are sent concurrently via asyncio.gather."""

    @pytest.mark.anyio
    async def test_notifies_all_members_except_author(self):
        """All SIG members except the author should receive notifications."""
        author_id = str(uuid.uuid4())
        sig_id = str(uuid.uuid4())
        post_id = str(uuid.uuid4())
        member1_id = str(uuid.uuid4())
        member2_id = str(uuid.uuid4())

        members = [_make_member(author_id), _make_member(member1_id), _make_member(member2_id)]

        mock_find_members = AsyncMock(return_value=(members, len(members)))
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

        # Author should NOT receive a notification — only member1 and member2
        assert mock_create.await_count == 2

    @pytest.mark.anyio
    async def test_handles_create_notification_failure(self):
        """Failures in individual notifications should not break the entire batch."""
        author_id = str(uuid.uuid4())
        sig_id = str(uuid.uuid4())
        post_id = str(uuid.uuid4())
        member_ids = [str(uuid.uuid4()) for _ in range(3)]

        members = [_make_member(mid) for mid in member_ids]

        mock_find_members = AsyncMock(return_value=(members, len(members)))
        mock_get_user = AsyncMock(return_value={"display_name": "Author"})
        # First call succeeds, second fails, third succeeds
        mock_create = AsyncMock(side_effect=[None, RuntimeError("DB error"), None])
        mock_check = AsyncMock(return_value=True)

        with (
            patch("app.repositories.sig_repo.find_members", mock_find_members),
            patch("app.services.user.get_user_by_id", mock_get_user),
            patch("app.services.notification.create_notification", mock_create),
            patch("app.event_handlers._check_idempotent", mock_check),
        ):
            # Should NOT raise
            await _on_post_created_in_sig(
                sig_id=sig_id,
                post_id=post_id,
                author_id=author_id,
                post_title="Test Post",
            )

        assert mock_create.await_count == 3


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
        """When the cap is reached, a warning should be logged."""
        author_id = str(uuid.uuid4())
        sig_id = str(uuid.uuid4())
        post_id = str(uuid.uuid4())

        total_members = _SIG_NOTIFICATION_MAX + 50
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
            patch("app.event_handlers.logger") as mock_logger,
        ):
            await _on_post_created_in_sig(
                sig_id=sig_id,
                post_id=post_id,
                author_id=author_id,
                post_title="Test Post",
            )

            # Should have logged a warning about cap being reached
            warning_calls = mock_logger.warning.call_args_list
            cap_warnings = [
                c for c in warning_calls if "cap" in str(c).lower()
            ]
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
            cap_warnings = [
                c for c in warning_calls if "cap" in str(c).lower()
            ]
            assert len(cap_warnings) == 0

    @pytest.mark.anyio
    async def test_deduplication_still_works(self):
        """Idempotency checks should still filter out duplicate notifications."""
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
            patch("app.event_handlers._check_idempotent", mock_check),
        ):
            await _on_post_created_in_sig(
                sig_id=sig_id,
                post_id=post_id,
                author_id=author_id,
                post_title="Test Post",
            )

        # Only 2 notifications should be created (third was deduplicated)
        assert mock_create.await_count == 2
