"""Tests for 2026-03-25 DM and Celery task audit fixes.

M-01: DM admin endpoint rate limiting
M-03: Banned sender cannot send DM
M-07: DM orphan quota cleanup task
M-08: File extension validation comments (structural -- verified by import)
L-12: Empty DM conversation cleanup task
L-13: All cleanup tasks have max_retries >= 2
H-08: DM_TEXT_EXPIRY_DAYS reduced to 7
"""

import uuid
from unittest.mock import AsyncMock, patch

import pytest

from tests.conftest import make_user_dict


# ---------------------------------------------------------------------------
# H-08: DM_TEXT_EXPIRY_DAYS is now 7
# ---------------------------------------------------------------------------


class TestDMTextExpiryDays:
    def test_dm_text_expiry_days_is_7(self) -> None:
        from app.core.constants import DM_TEXT_EXPIRY_DAYS

        assert DM_TEXT_EXPIRY_DAYS == 7, (
            f"DM_TEXT_EXPIRY_DAYS should be 7, got {DM_TEXT_EXPIRY_DAYS}"
        )


# ---------------------------------------------------------------------------
# M-01: RATE_LIMIT_DM_ADMIN constant exists
# ---------------------------------------------------------------------------


class TestRateLimitDMAdmin:
    def test_rate_limit_dm_admin_exists(self) -> None:
        from app.core.constants import RATE_LIMIT_DM_ADMIN

        assert isinstance(RATE_LIMIT_DM_ADMIN, tuple)
        assert len(RATE_LIMIT_DM_ADMIN) == 2
        max_val, window = RATE_LIMIT_DM_ADMIN
        assert max_val == 30
        assert window == 60


# ---------------------------------------------------------------------------
# M-01: DM admin endpoint rate limiting (mock check_rate_limit -> False -> 429)
# ---------------------------------------------------------------------------


class TestDMAdminRateLimit:
    @pytest.mark.asyncio
    @patch(
        "app.core.deps.get_user_by_id",
        new_callable=AsyncMock,
        return_value={"is_banned": False},
    )
    @patch("app.core.deps.validate_session", new_callable=AsyncMock, return_value=True)
    async def test_admin_list_messages_rate_limited(
        self, mock_session, mock_user, client, auth_headers
    ) -> None:
        """When check_rate_limit returns False, admin endpoint returns 429."""
        conversation_id = str(uuid.uuid4())
        headers, admin_id, _ = auth_headers("SUPER_ADMIN")

        with patch(
            "app.api.v1.endpoints.dm.check_rate_limit",
            new_callable=AsyncMock,
            return_value=False,
        ):
            resp = await client.get(
                f"/api/v1/dm/admin/conversations/{conversation_id}/messages",
                headers=headers,
            )
            assert resp.status_code == 429

    @pytest.mark.asyncio
    @patch(
        "app.core.deps.get_user_by_id",
        new_callable=AsyncMock,
        return_value={"is_banned": False},
    )
    @patch("app.core.deps.validate_session", new_callable=AsyncMock, return_value=True)
    async def test_admin_list_messages_passes_when_not_rate_limited(
        self, mock_session, mock_user, client, auth_headers
    ) -> None:
        """When check_rate_limit returns True, admin endpoint proceeds (not 429)."""
        conversation_id = str(uuid.uuid4())
        headers, admin_id, _ = auth_headers("SUPER_ADMIN")

        with (
            patch(
                "app.api.v1.endpoints.dm.check_rate_limit",
                new_callable=AsyncMock,
                return_value=True,
            ),
            patch(
                "app.repositories.dm_repo.find_messages",
                new_callable=AsyncMock,
                return_value=([], 0),
            ),
        ):
            resp = await client.get(
                f"/api/v1/dm/admin/conversations/{conversation_id}/messages",
                headers=headers,
            )
            # Should not be 429 -- the request proceeds past rate limiting
            assert resp.status_code != 429


# ---------------------------------------------------------------------------
# M-03: Banned sender cannot send DM
# ---------------------------------------------------------------------------


class TestBannedSenderCannotSendDM:
    @pytest.mark.asyncio
    async def test_banned_sender_raises_403(self) -> None:
        """A banned user should be rejected with 403 when trying to send a DM."""
        from app.core.errors import AppError
        from app.services.dm import send_message

        sender_id = str(uuid.uuid4())
        recipient_id = str(uuid.uuid4())

        banned_user = make_user_dict(user_id=sender_id, is_banned=True)

        with patch(
            "app.repositories.user_repo.find_by_id",
            new_callable=AsyncMock,
            return_value=banned_user,
        ):
            with pytest.raises(AppError) as exc_info:
                await send_message(
                    sender_id=sender_id,
                    recipient_id=recipient_id,
                    content="Hello!",
                )
            assert exc_info.value.status_code == 403
            assert "banned" in exc_info.value.detail["message"].lower()

    @pytest.mark.asyncio
    async def test_non_banned_sender_proceeds_to_recipient_check(self) -> None:
        """A non-banned user should pass the sender ban check and fail on recipient."""
        from app.core.errors import AppError
        from app.services.dm import send_message

        sender_id = str(uuid.uuid4())
        recipient_id = str(uuid.uuid4())

        normal_sender = make_user_dict(user_id=sender_id, is_banned=False)
        deleted_recipient = make_user_dict(user_id=recipient_id, is_deleted=True)

        call_count = 0

        async def mock_find_by_id(uid: uuid.UUID) -> dict:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return normal_sender  # sender lookup
            return deleted_recipient  # recipient lookup

        with patch(
            "app.repositories.user_repo.find_by_id",
            new_callable=AsyncMock,
            side_effect=mock_find_by_id,
        ):
            with pytest.raises(AppError) as exc_info:
                await send_message(
                    sender_id=sender_id,
                    recipient_id=recipient_id,
                    content="Hello!",
                )
            # Should fail on recipient check (deleted), NOT on sender ban
            assert exc_info.value.status_code == 404
            assert "recipient" in exc_info.value.detail["message"].lower()


# ---------------------------------------------------------------------------
# M-07: Orphan quota cleanup task exists
# ---------------------------------------------------------------------------


class TestOrphanQuotaCleanupTask:
    def test_cleanup_dm_orphan_quotas_task_exists(self) -> None:
        from app.tasks.cleanup import cleanup_dm_orphan_quotas

        assert callable(cleanup_dm_orphan_quotas)
        assert cleanup_dm_orphan_quotas.name == "cleanup_dm_orphan_quotas"

    def test_cleanup_dm_orphan_quotas_has_correct_retries(self) -> None:
        from app.tasks.cleanup import cleanup_dm_orphan_quotas

        assert cleanup_dm_orphan_quotas.max_retries >= 2


# ---------------------------------------------------------------------------
# L-12: Empty DM conversation cleanup task exists
# ---------------------------------------------------------------------------


class TestEmptyConversationCleanupTask:
    def test_cleanup_empty_dm_conversations_task_exists(self) -> None:
        from app.tasks.cleanup import cleanup_empty_dm_conversations

        assert callable(cleanup_empty_dm_conversations)
        assert cleanup_empty_dm_conversations.name == "cleanup_empty_dm_conversations"

    def test_cleanup_empty_dm_conversations_has_correct_retries(self) -> None:
        from app.tasks.cleanup import cleanup_empty_dm_conversations

        assert cleanup_empty_dm_conversations.max_retries >= 2


# ---------------------------------------------------------------------------
# L-13: All cleanup tasks have max_retries >= 2
# ---------------------------------------------------------------------------


class TestCleanupTaskRetries:
    """All cleanup-related Celery tasks should have max_retries >= 2."""

    @pytest.mark.parametrize(
        "task_module,task_attr",
        [
            ("app.tasks.cleanup", "sync_guest_counter_task"),
            ("app.tasks.cleanup", "cleanup_old_file_scans"),
            ("app.tasks.cleanup", "cleanup_old_audit_logs"),
            ("app.tasks.cleanup", "cleanup_old_read_notifications"),
            ("app.tasks.cleanup", "cleanup_orphan_files"),
            ("app.tasks.cleanup", "cleanup_dm_orphan_quotas"),
            ("app.tasks.cleanup", "cleanup_empty_dm_conversations"),
            ("app.tasks.recommendations", "compute_friend_recommendations"),
            ("app.tasks.view_sync", "reconcile_counters"),
            ("app.tasks.form_autoclose", "auto_close_expired_forms"),
        ],
    )
    def test_max_retries_at_least_2(self, task_module: str, task_attr: str) -> None:
        import importlib

        mod = importlib.import_module(task_module)
        task = getattr(mod, task_attr)
        assert task.max_retries >= 2, (
            f"{task_module}.{task_attr} has max_retries={task.max_retries}, expected >= 2"
        )

    @pytest.mark.parametrize(
        "task_module,task_attr",
        [
            ("app.tasks.cleanup", "sync_guest_counter_task"),
            ("app.tasks.cleanup", "cleanup_old_file_scans"),
            ("app.tasks.cleanup", "cleanup_old_audit_logs"),
            ("app.tasks.cleanup", "cleanup_old_read_notifications"),
            ("app.tasks.cleanup", "cleanup_orphan_files"),
            ("app.tasks.cleanup", "cleanup_dm_orphan_quotas"),
            ("app.tasks.cleanup", "cleanup_empty_dm_conversations"),
        ],
    )
    def test_has_default_retry_delay(self, task_module: str, task_attr: str) -> None:
        import importlib

        mod = importlib.import_module(task_module)
        task = getattr(mod, task_attr)
        assert task.default_retry_delay == 30, (
            f"{task_module}.{task_attr} default_retry_delay={task.default_retry_delay}, expected 30"
        )
