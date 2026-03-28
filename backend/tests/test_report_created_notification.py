"""Tests for report.created event → admin notification flow."""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest

from app.event_handlers import _on_report_created


class TestOnReportCreated:
    """Unit tests for _on_report_created event handler."""

    @pytest.mark.anyio
    async def test_notifies_all_admins(self):
        """Handler creates a notification for every ADMIN and SUPER_ADMIN."""
        admin1 = uuid.uuid4()
        admin2 = uuid.uuid4()
        reporter_uid = str(uuid.uuid4())
        report_id = str(uuid.uuid4())
        post_id = str(uuid.uuid4())

        mock_find = AsyncMock(return_value=[admin1, admin2])
        mock_create = AsyncMock(return_value={"id": str(uuid.uuid4())})
        mock_redis = AsyncMock()
        mock_redis.set = AsyncMock(return_value=True)

        with (
            patch("app.repositories.user_repo.find_ids_by_roles", mock_find),
            patch("app.services.notification.create_notification", mock_create),
            patch("app.core.redis.get_redis", return_value=mock_redis),
        ):
            await _on_report_created(
                reporter_uid=reporter_uid,
                report_id=report_id,
                post_id=post_id,
                post_title="Spam Post",
            )

        mock_find.assert_awaited_once_with(["ADMIN", "SUPER_ADMIN"])
        assert mock_create.await_count == 2

        calls = mock_create.await_args_list
        notified_ids = {c.kwargs["user_id"] for c in calls}
        assert notified_ids == {str(admin1), str(admin2)}
        for call in calls:
            assert "Spam Post" in call.kwargs["message"]
            assert call.kwargs["action_type"] == "SYSTEM"
            assert call.kwargs["entity_type"] == "report"
            assert call.kwargs["entity_id"] == report_id

    @pytest.mark.anyio
    async def test_no_admins_no_notifications(self):
        """If there are no admins, no notifications are created."""
        mock_find = AsyncMock(return_value=[])
        mock_create = AsyncMock()

        with (
            patch("app.repositories.user_repo.find_ids_by_roles", mock_find),
            patch("app.services.notification.create_notification", mock_create),
        ):
            await _on_report_created(
                reporter_uid=str(uuid.uuid4()),
                report_id=str(uuid.uuid4()),
                post_id=str(uuid.uuid4()),
                post_title="Test",
            )

        mock_create.assert_not_awaited()

    @pytest.mark.anyio
    async def test_raises_when_find_admins_fails(self):
        """Handler re-raises if fetching admin IDs fails (event bus retries)."""
        mock_find = AsyncMock(side_effect=RuntimeError("pool closed"))

        with (
            patch("app.repositories.user_repo.find_ids_by_roles", mock_find),
            pytest.raises(RuntimeError, match="pool closed"),
        ):
            await _on_report_created(
                reporter_uid=str(uuid.uuid4()),
                report_id=str(uuid.uuid4()),
                post_id=str(uuid.uuid4()),
                post_title="Fail",
            )

    @pytest.mark.anyio
    async def test_skips_already_sent_on_retry(self):
        """On retry, handler skips admins whose dedup key already exists."""
        admin1 = uuid.uuid4()
        mock_find = AsyncMock(return_value=[admin1])
        mock_create = AsyncMock(side_effect=RuntimeError("DB error"))
        mock_redis = AsyncMock()
        mock_redis.exists = AsyncMock(return_value=True)

        with (
            patch("app.repositories.user_repo.find_ids_by_roles", mock_find),
            patch("app.services.notification.create_notification", mock_create),
            patch("app.core.redis.get_redis", return_value=mock_redis),
        ):
            await _on_report_created(
                reporter_uid=str(uuid.uuid4()),
                report_id=str(uuid.uuid4()),
                post_id=str(uuid.uuid4()),
                post_title="Retry",
            )

    @pytest.mark.anyio
    async def test_continues_on_single_admin_failure_then_raises(self):
        """If notification fails for one admin, others still get notified, then re-raises."""
        admin1 = uuid.uuid4()
        admin2 = uuid.uuid4()
        call_count = 0

        async def _create_side_effect(**kwargs):
            nonlocal call_count
            call_count += 1
            if kwargs["user_id"] == str(admin1):
                raise RuntimeError("DB error")
            return {"id": str(uuid.uuid4())}

        mock_find = AsyncMock(return_value=[admin1, admin2])
        mock_create = AsyncMock(side_effect=_create_side_effect)
        mock_redis = AsyncMock()
        mock_redis.set = AsyncMock(return_value=True)
        mock_redis.exists = AsyncMock(return_value=False)

        with (
            patch("app.repositories.user_repo.find_ids_by_roles", mock_find),
            patch("app.services.notification.create_notification", mock_create),
            patch("app.core.redis.get_redis", return_value=mock_redis),
            pytest.raises(RuntimeError, match="Failed to notify 1/2 admin"),
        ):
            await _on_report_created(
                reporter_uid=str(uuid.uuid4()),
                report_id=str(uuid.uuid4()),
                post_id=str(uuid.uuid4()),
                post_title="Partial",
            )

        assert call_count == 2


class TestCreateReportEmitsEvent:
    """Test that create_report service emits report.created event."""

    @pytest.mark.anyio
    async def test_emit_called_on_success(self):
        """create_report emits report.created after successful insert."""
        user_id = str(uuid.uuid4())
        post_id = uuid.uuid4()
        report_id = uuid.uuid4()
        mock_post = {"id": str(post_id), "user_id": str(uuid.uuid4()), "title": "Bad Post"}
        mock_row = {
            "id": report_id,
            "post_id": post_id,
            "user_id": uuid.UUID(user_id),
            "reason": "Spam",
            "status": "PENDING",
            "reviewed_by": None,
            "reviewed_at": None,
            "created_at": datetime(2026, 1, 1, tzinfo=timezone.utc),
        }
        mock_emit = AsyncMock()

        with (
            patch("app.repositories.post_repo.find_by_id", AsyncMock(return_value=mock_post)),
            patch("app.repositories.report_repo.insert", AsyncMock(return_value=mock_row)),
            patch("app.core.event_bus.emit", mock_emit),
        ):
            from app.services.report import create_report

            await create_report(post_id, user_id, "Spam")

        mock_emit.assert_awaited_once()
        call_kwargs = mock_emit.await_args
        assert call_kwargs[0][0] == "report.created"
        assert call_kwargs[1]["reporter_uid"] == user_id
        assert call_kwargs[1]["post_title"] == "Bad Post"

    @pytest.mark.anyio
    async def test_emit_failure_does_not_crash(self):
        """create_report returns row even if emit() raises."""
        user_id = str(uuid.uuid4())
        post_id = uuid.uuid4()
        mock_post = {"id": str(post_id), "user_id": str(uuid.uuid4()), "title": "Bad Post"}
        mock_row = {
            "id": uuid.uuid4(),
            "post_id": post_id,
            "user_id": uuid.UUID(user_id),
            "reason": "Spam",
            "status": "PENDING",
            "reviewed_by": None,
            "reviewed_at": None,
            "created_at": datetime(2026, 1, 1, tzinfo=timezone.utc),
        }
        mock_emit = AsyncMock(side_effect=RuntimeError("Redis down"))

        with (
            patch("app.repositories.post_repo.find_by_id", AsyncMock(return_value=mock_post)),
            patch("app.repositories.report_repo.insert", AsyncMock(return_value=mock_row)),
            patch("app.core.event_bus.emit", mock_emit),
        ):
            from app.services.report import create_report

            result = await create_report(post_id, user_id, "Spam")

        assert result is not None
