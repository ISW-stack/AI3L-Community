"""Tests for service-layer bug fixes:
- Bug #3: Report review sends notification to reporter
- Bug #4: Dashboard stats partial failure returns 0 for failed stats
- Bug #5: File upload rollback when storage increment fails
"""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# =========================================================================
# Bug #3: Report review notification
# =========================================================================

_REPORT_SVC = "app.services.report"
_NOTIF_SVC = "app.services.notification"


class TestReportReviewNotification:
    """Verify review_report sends a notification to the reporter."""

    @pytest.mark.anyio
    async def test_review_resolved_notifies_reporter(self):
        """Reviewing a report as RESOLVED should create a notification for the reporter."""
        report_id = uuid.uuid4()
        reviewer_id = str(uuid.uuid4())
        reporter_id = uuid.uuid4()
        now = datetime.now(timezone.utc)

        raw_row = {
            "id": report_id,
            "post_id": uuid.uuid4(),
            "user_id": reporter_id,
            "reason": "Spam",
            "status": "RESOLVED",
            "reviewed_by": uuid.UUID(reviewer_id),
            "reviewed_at": now,
            "created_at": now,
            "updated_at": now,
        }

        mock_update = AsyncMock(return_value=raw_row)
        mock_create_notif = AsyncMock(return_value={"id": str(uuid.uuid4())})

        with (
            patch(f"{_REPORT_SVC}.report_repo.update_status", mock_update),
            patch(f"{_NOTIF_SVC}.create_notification", mock_create_notif),
        ):
            from app.services.report import review_report

            result = await review_report(report_id, reviewer_id, "RESOLVED")

        assert result is not None
        mock_create_notif.assert_awaited_once()
        call_kwargs = mock_create_notif.call_args
        assert call_kwargs[1]["user_id"] == str(reporter_id)
        assert call_kwargs[1]["action_type"] == "report_reviewed"
        assert "resolved" in call_kwargs[1]["message"]

    @pytest.mark.anyio
    async def test_review_dismissed_notifies_reporter(self):
        """Reviewing a report as DISMISSED should notify with 'dismissed' text."""
        report_id = uuid.uuid4()
        reviewer_id = str(uuid.uuid4())
        reporter_id = uuid.uuid4()
        now = datetime.now(timezone.utc)

        raw_row = {
            "id": report_id,
            "post_id": uuid.uuid4(),
            "user_id": reporter_id,
            "reason": "Not spam",
            "status": "DISMISSED",
            "reviewed_by": uuid.UUID(reviewer_id),
            "reviewed_at": now,
            "created_at": now,
            "updated_at": now,
        }

        mock_update = AsyncMock(return_value=raw_row)
        mock_create_notif = AsyncMock(return_value={"id": str(uuid.uuid4())})

        with (
            patch(f"{_REPORT_SVC}.report_repo.update_status", mock_update),
            patch(f"{_NOTIF_SVC}.create_notification", mock_create_notif),
        ):
            from app.services.report import review_report

            result = await review_report(report_id, reviewer_id, "DISMISSED")

        assert result is not None
        call_kwargs = mock_create_notif.call_args
        assert "dismissed" in call_kwargs[1]["message"]

    @pytest.mark.anyio
    async def test_review_notification_failure_does_not_crash(self):
        """If notification creation fails, review_report should still return the report."""
        report_id = uuid.uuid4()
        reviewer_id = str(uuid.uuid4())
        reporter_id = uuid.uuid4()
        now = datetime.now(timezone.utc)

        raw_row = {
            "id": report_id,
            "post_id": uuid.uuid4(),
            "user_id": reporter_id,
            "reason": "Spam",
            "status": "RESOLVED",
            "reviewed_by": uuid.UUID(reviewer_id),
            "reviewed_at": now,
            "created_at": now,
            "updated_at": now,
        }

        mock_update = AsyncMock(return_value=raw_row)
        mock_create_notif = AsyncMock(side_effect=RuntimeError("DB down"))

        with (
            patch(f"{_REPORT_SVC}.report_repo.update_status", mock_update),
            patch(f"{_NOTIF_SVC}.create_notification", mock_create_notif),
        ):
            from app.services.report import review_report

            result = await review_report(report_id, reviewer_id, "RESOLVED")

        # Should still return the report even though notification failed
        assert result is not None

    @pytest.mark.anyio
    async def test_review_not_found_returns_none(self):
        """If report not found, should return None without attempting notification."""
        mock_update = AsyncMock(return_value=None)
        mock_create_notif = AsyncMock()

        with (
            patch(f"{_REPORT_SVC}.report_repo.update_status", mock_update),
            patch(f"{_NOTIF_SVC}.create_notification", mock_create_notif),
        ):
            from app.services.report import review_report

            result = await review_report(uuid.uuid4(), str(uuid.uuid4()), "RESOLVED")

        assert result is None
        mock_create_notif.assert_not_awaited()


# =========================================================================
# Bug #4: Dashboard stats partial failure
# =========================================================================

_DASH_REPO = "app.services.dashboard.dashboard_repo"


class TestDashboardPartialFailure:
    """Verify get_dashboard_stats returns 0 for failed stats instead of crashing."""

    @pytest.mark.anyio
    async def test_all_stats_succeed(self):
        """Normal case: all stats returned correctly."""
        with (
            patch(f"{_DASH_REPO}.count_users", new_callable=AsyncMock, return_value=10),
            patch(f"{_DASH_REPO}.count_posts", new_callable=AsyncMock, return_value=20),
            patch(f"{_DASH_REPO}.count_sigs", new_callable=AsyncMock, return_value=3),
            patch(f"{_DASH_REPO}.count_forms", new_callable=AsyncMock, return_value=5),
            patch(f"{_DASH_REPO}.count_pending_reports", new_callable=AsyncMock, return_value=2),
            patch(
                f"{_DASH_REPO}.count_pending_applications",
                new_callable=AsyncMock,
                return_value=1,
            ),
        ):
            from app.services.dashboard import get_dashboard_stats

            stats = await get_dashboard_stats()

        assert stats["users"] == 10
        assert stats["posts"] == 20
        assert stats["sigs"] == 3
        assert stats["forms"] == 5
        assert stats["pending_reports"] == 2
        assert stats["pending_applications"] == 1

    @pytest.mark.anyio
    async def test_single_stat_failure_returns_zero(self):
        """If one stat query fails, it should return 0 while others succeed."""
        with (
            patch(
                f"{_DASH_REPO}.count_users",
                new_callable=AsyncMock,
                side_effect=RuntimeError("DB error"),
            ),
            patch(f"{_DASH_REPO}.count_posts", new_callable=AsyncMock, return_value=20),
            patch(f"{_DASH_REPO}.count_sigs", new_callable=AsyncMock, return_value=3),
            patch(f"{_DASH_REPO}.count_forms", new_callable=AsyncMock, return_value=5),
            patch(f"{_DASH_REPO}.count_pending_reports", new_callable=AsyncMock, return_value=2),
            patch(
                f"{_DASH_REPO}.count_pending_applications",
                new_callable=AsyncMock,
                return_value=1,
            ),
        ):
            from app.services.dashboard import get_dashboard_stats

            stats = await get_dashboard_stats()

        assert stats["users"] == 0  # failed stat defaults to 0
        assert stats["posts"] == 20
        assert stats["sigs"] == 3

    @pytest.mark.anyio
    async def test_all_stats_fail_returns_all_zeros(self):
        """If all stat queries fail, all values should be 0."""
        with (
            patch(
                f"{_DASH_REPO}.count_users",
                new_callable=AsyncMock,
                side_effect=RuntimeError("fail"),
            ),
            patch(
                f"{_DASH_REPO}.count_posts",
                new_callable=AsyncMock,
                side_effect=RuntimeError("fail"),
            ),
            patch(
                f"{_DASH_REPO}.count_sigs",
                new_callable=AsyncMock,
                side_effect=RuntimeError("fail"),
            ),
            patch(
                f"{_DASH_REPO}.count_forms",
                new_callable=AsyncMock,
                side_effect=RuntimeError("fail"),
            ),
            patch(
                f"{_DASH_REPO}.count_pending_reports",
                new_callable=AsyncMock,
                side_effect=RuntimeError("fail"),
            ),
            patch(
                f"{_DASH_REPO}.count_pending_applications",
                new_callable=AsyncMock,
                side_effect=RuntimeError("fail"),
            ),
        ):
            from app.services.dashboard import get_dashboard_stats

            stats = await get_dashboard_stats()

        assert all(v == 0 for v in stats.values())
        assert len(stats) == 6


# =========================================================================
# Bug #5: File upload rollback on storage increment failure
# =========================================================================

_FILES_EP = "app.api.v1.endpoints.files"


class TestFileUploadRollback:
    """Verify uploaded file is deleted when storage increment fails."""

    def _override_auth(self, role="MEMBER", user_id=None):
        from app.core.deps import get_current_user
        from app.main import app

        uid = user_id or str(uuid.uuid4())
        payload = {"sub": uid, "role": role, "jti": str(uuid.uuid4())}
        app.dependency_overrides[get_current_user] = lambda: payload
        return payload, uid

    def _clear_overrides(self):
        from app.main import app

        app.dependency_overrides.clear()

    @pytest.mark.anyio
    async def test_rollback_deletes_file_on_increment_failure(self, client):
        """When increment_storage_used fails, the uploaded file should be deleted."""
        payload, uid = self._override_auth("MEMBER")

        mock_upload = AsyncMock(return_value="editor/key/file.png")
        mock_delete = AsyncMock()
        mock_get_storage = AsyncMock(return_value=0)
        mock_increment = AsyncMock(side_effect=RuntimeError("DB down"))
        mock_rate_limit = AsyncMock(return_value=True)
        mock_redis = AsyncMock()
        mock_redis.set = AsyncMock(return_value=True)
        mock_redis.delete = AsyncMock()
        mock_validate = MagicMock(return_value=("image/png", b"fake-png-data"))

        try:
            with (
                patch(f"{_FILES_EP}.async_upload_file", mock_upload),
                patch(f"{_FILES_EP}.async_delete_file", mock_delete),
                patch(f"{_FILES_EP}.user_repo.get_storage_used", mock_get_storage),
                patch(f"{_FILES_EP}.user_repo.increment_storage_used", mock_increment),
                patch(f"{_FILES_EP}.check_rate_limit", mock_rate_limit),
                patch(f"{_FILES_EP}.get_redis", return_value=mock_redis),
                patch(f"{_FILES_EP}.validate_editor_file", mock_validate),
                patch(f"{_FILES_EP}.file_scan_repo.insert", new_callable=AsyncMock),
            ):
                resp = await client.post(
                    "/api/v1/files/upload/editor",
                    files={"file": ("test.png", b"fake-png-data", "image/png")},
                    headers={"Authorization": "Bearer fake"},
                )

            assert resp.status_code == 500
            assert "Upload failed" in resp.json()["detail"]
            mock_delete.assert_awaited_once()  # rollback deletion called
        finally:
            self._clear_overrides()

    @pytest.mark.anyio
    async def test_successful_upload_no_rollback(self, client):
        """When increment succeeds, no rollback should occur."""
        payload, uid = self._override_auth("MEMBER")

        mock_upload = AsyncMock(return_value="editor/key/file.png")
        mock_delete = AsyncMock()
        mock_get_storage = AsyncMock(return_value=0)
        mock_increment = AsyncMock()
        mock_rate_limit = AsyncMock(return_value=True)
        mock_redis = AsyncMock()
        mock_redis.set = AsyncMock(return_value=True)
        mock_redis.delete = AsyncMock()
        mock_validate = MagicMock(return_value=("image/png", b"fake-png-data"))

        try:
            with (
                patch(f"{_FILES_EP}.async_upload_file", mock_upload),
                patch(f"{_FILES_EP}.async_delete_file", mock_delete),
                patch(f"{_FILES_EP}.user_repo.get_storage_used", mock_get_storage),
                patch(f"{_FILES_EP}.user_repo.increment_storage_used", mock_increment),
                patch(f"{_FILES_EP}.check_rate_limit", mock_rate_limit),
                patch(f"{_FILES_EP}.get_redis", return_value=mock_redis),
                patch(f"{_FILES_EP}.validate_editor_file", mock_validate),
                patch(f"{_FILES_EP}.file_scan_repo.insert", new_callable=AsyncMock),
            ):
                resp = await client.post(
                    "/api/v1/files/upload/editor",
                    files={"file": ("test.png", b"fake-png-data", "image/png")},
                    headers={"Authorization": "Bearer fake"},
                )

            assert resp.status_code == 201
            mock_delete.assert_not_awaited()  # no rollback
            mock_increment.assert_awaited_once()
        finally:
            self._clear_overrides()
