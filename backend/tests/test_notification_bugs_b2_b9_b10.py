"""Tests for notification bug fixes B2, B9, B10."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

_REPO = "app.repositories.notification_repo"
_SVC = "app.services.notification"


class TestB2UnreadCountExcludesBlockedUsers:
    """B2: find_many() unread_count must respect exclude_user_ids."""

    @pytest.mark.anyio
    async def test_unread_count_excludes_blocked_users(self):
        """When exclude_user_ids is provided, the unread_count query should
        filter out notifications from those users."""
        user_id = uuid.uuid4()
        blocked_id = uuid.uuid4()

        # Build fake rows with _total
        notif_row = {
            "id": uuid.uuid4(),
            "user_id": user_id,
            "trigger_user_id": uuid.uuid4(),  # not blocked
            "action_type": "MENTION",
            "entity_type": "post",
            "entity_id": uuid.uuid4(),
            "message": "test",
            "is_read": False,
            "created_at": "2026-01-01T00:00:00+00:00",
            "trigger_display_name": "User",
            "trigger_avatar_url": None,
            "_total": 1,
        }

        mock_record = MagicMock()
        mock_record.__getitem__ = lambda s, k: notif_row[k]
        mock_record.items = lambda s: notif_row.items()

        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(return_value=[mock_record])
        mock_conn.fetchval = AsyncMock(return_value=1)

        mock_pool = MagicMock()
        mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

        with patch(f"{_REPO}.get_pool", return_value=mock_pool):
            from app.repositories.notification_repo import find_many

            _rows, _total, _unread = await find_many(
                user_id,
                unread_only=False,
                page_size=20,
                offset=0,
                exclude_user_ids=[blocked_id],
            )

        # Verify the unread_count query (fetchval) included the blocked filter
        fetchval_call = mock_conn.fetchval.call_args
        query = fetchval_call[0][0]
        assert "trigger_user_id" in query, "Unread count query must filter by trigger_user_id"
        assert "ALL(" in query, "Unread count query must use ALL() for exclude_user_ids"
        # The blocked_id should be passed as a parameter
        assert [blocked_id] in fetchval_call[0], "Blocked user ID list must be passed as query parameter"

    @pytest.mark.anyio
    async def test_unread_count_no_exclusion_when_no_blocked(self):
        """When exclude_user_ids is None, unread_count query should be simple."""
        user_id = uuid.uuid4()

        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(return_value=[])
        mock_conn.fetchval = AsyncMock(side_effect=[0, 0])  # fallback count + unread

        mock_pool = MagicMock()
        mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

        with patch(f"{_REPO}.get_pool", return_value=mock_pool):
            from app.repositories.notification_repo import find_many

            await find_many(user_id, exclude_user_ids=None)

        # The unread count fetchval should NOT contain trigger_user_id filter
        # It's the second fetchval call (first is for the fallback total count)
        calls = mock_conn.fetchval.call_args_list
        unread_query = calls[-1][0][0]
        assert "ALL(" not in unread_query, "Without exclusions, no ALL() filter expected"


class TestB9RedisExceptionLogging:
    """B9: Redis failure during list_notifications should log a warning."""

    @pytest.mark.anyio
    async def test_redis_failure_logs_warning(self):
        """When get_redis() raises, a warning should be logged."""
        user_id = str(uuid.uuid4())

        with (
            patch(f"{_SVC}.get_redis", side_effect=Exception("Redis down")),
            patch(f"{_SVC}.logger") as mock_logger,
            patch(f"{_SVC}.notification_repo") as mock_repo,
        ):
            mock_repo.find_many = AsyncMock(return_value=([], 0, 0))

            from app.services.notification import list_notifications

            await list_notifications(user_id)

            mock_logger.warning.assert_called_once()
            assert "blocked user" in mock_logger.warning.call_args[0][0].lower()

    @pytest.mark.anyio
    async def test_redis_failure_still_returns_results(self):
        """Even when Redis fails, notifications should still be returned."""
        user_id = str(uuid.uuid4())

        fake_notifs = [{"id": str(uuid.uuid4()), "action_type": "MENTION"}]
        fake_converted = {"id": "converted"}

        with (
            patch(f"{_SVC}.get_redis", side_effect=Exception("Redis down")),
            patch(f"{_SVC}.logger"),
            patch(f"{_SVC}.notification_repo") as mock_repo,
            patch(f"{_SVC}.async_row_to_notification", new_callable=AsyncMock, return_value=fake_converted),
        ):
            mock_repo.find_many = AsyncMock(return_value=(fake_notifs, 1, 1))

            from app.services.notification import list_notifications

            notifs, total, unread = await list_notifications(user_id)

            assert total == 1
            assert len(notifs) == 1
            # exclude_user_ids should be None since Redis failed
            call_kwargs = mock_repo.find_many.call_args
            assert call_kwargs.kwargs.get("exclude_user_ids") is None


class TestB10DeadCodeRemoved:
    """B10: page_size == 0 branch is removed; count_unread() is the proper way."""

    @pytest.mark.anyio
    async def test_find_many_no_zero_page_size_branch(self):
        """Verify the page_size == 0 special case no longer exists in source."""
        import inspect

        from app.repositories.notification_repo import find_many

        source = inspect.getsource(find_many)
        assert "page_size == 0" not in source, "Dead code page_size == 0 branch should be removed"

    @pytest.mark.anyio
    async def test_count_unread_still_works(self):
        """count_unread() should still function as the proper way to get unread count."""
        user_id = uuid.uuid4()

        mock_conn = AsyncMock()
        mock_conn.fetchval = AsyncMock(return_value=5)

        mock_pool = MagicMock()
        mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

        with patch(f"{_REPO}.get_pool", return_value=mock_pool):
            from app.repositories.notification_repo import count_unread

            result = await count_unread(user_id)

        assert result == 5
