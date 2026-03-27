"""Tests for application.created event → admin notification flow."""

import uuid
from unittest.mock import AsyncMock, patch

import pytest

from app.event_handlers import _on_application_created


class TestOnApplicationCreated:
    """Unit tests for _on_application_created event handler."""

    @pytest.mark.anyio
    async def test_notifies_all_admins(self):
        """Handler creates a notification for every ADMIN and SUPER_ADMIN."""
        admin1 = uuid.uuid4()
        admin2 = uuid.uuid4()
        applicant_uid = str(uuid.uuid4())
        display_name = "Test User"

        mock_find = AsyncMock(return_value=[admin1, admin2])
        mock_create = AsyncMock(return_value={"id": str(uuid.uuid4())})
        mock_idemp = AsyncMock(return_value=True)

        with (
            patch("app.repositories.user_repo.find_ids_by_roles", mock_find),
            patch("app.services.notification.create_notification", mock_create),
            patch("app.event_handlers._check_idempotent", mock_idemp),
        ):
            await _on_application_created(
                applicant_uid=applicant_uid,
                display_name=display_name,
            )

        mock_find.assert_awaited_once_with(["ADMIN", "SUPER_ADMIN"])
        assert mock_create.await_count == 2

        # Verify both admins got notified with correct message
        calls = mock_create.await_args_list
        notified_ids = {c.kwargs["user_id"] for c in calls}
        assert notified_ids == {str(admin1), str(admin2)}
        for call in calls:
            assert "Test User" in call.kwargs["message"]
            assert call.kwargs["action_type"] == "SYSTEM"
            assert call.kwargs["entity_type"] == "application"

    @pytest.mark.anyio
    async def test_skips_duplicate_via_idempotency(self):
        """Handler skips notification if idempotency check returns False."""
        admin1 = uuid.uuid4()
        mock_find = AsyncMock(return_value=[admin1])
        mock_create = AsyncMock()
        mock_idemp = AsyncMock(return_value=False)  # duplicate

        with (
            patch("app.repositories.user_repo.find_ids_by_roles", mock_find),
            patch("app.services.notification.create_notification", mock_create),
            patch("app.event_handlers._check_idempotent", mock_idemp),
        ):
            await _on_application_created(
                applicant_uid=str(uuid.uuid4()),
                display_name="Dup User",
            )

        mock_create.assert_not_awaited()

    @pytest.mark.anyio
    async def test_continues_on_single_admin_failure(self):
        """If notification fails for one admin, others still get notified."""
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
        mock_idemp = AsyncMock(return_value=True)

        with (
            patch("app.repositories.user_repo.find_ids_by_roles", mock_find),
            patch("app.services.notification.create_notification", mock_create),
            patch("app.event_handlers._check_idempotent", mock_idemp),
        ):
            await _on_application_created(
                applicant_uid=str(uuid.uuid4()),
                display_name="Resilient User",
            )

        # Both were attempted
        assert call_count == 2

    @pytest.mark.anyio
    async def test_raises_when_find_admins_fails(self):
        """Handler re-raises if fetching admin IDs fails (event bus retries)."""
        mock_find = AsyncMock(side_effect=RuntimeError("pool closed"))

        with (
            patch("app.repositories.user_repo.find_ids_by_roles", mock_find),
            pytest.raises(RuntimeError, match="pool closed"),
        ):
            await _on_application_created(
                applicant_uid=str(uuid.uuid4()),
                display_name="Fail User",
            )

    @pytest.mark.anyio
    async def test_no_admins_no_notifications(self):
        """If there are no admins, no notifications are created."""
        mock_find = AsyncMock(return_value=[])
        mock_create = AsyncMock()
        mock_idemp = AsyncMock(return_value=True)

        with (
            patch("app.repositories.user_repo.find_ids_by_roles", mock_find),
            patch("app.services.notification.create_notification", mock_create),
            patch("app.event_handlers._check_idempotent", mock_idemp),
        ):
            await _on_application_created(
                applicant_uid=str(uuid.uuid4()),
                display_name="No Admin User",
            )

        mock_create.assert_not_awaited()


class TestCreateApplicationEmitsEvent:
    """Test that create_application service emits application.created event."""

    @pytest.mark.anyio
    async def test_emit_called_on_success(self):
        """create_application emits application.created after successful insert."""
        guest_id = uuid.uuid4()
        mock_row = {
            "id": uuid.uuid4(),
            "user_id": guest_id,
            "status": "PENDING",
        }
        mock_insert = AsyncMock(return_value=mock_row)
        mock_hash = AsyncMock(return_value="hashed")
        mock_emit = AsyncMock()

        with (
            patch("app.services.application.application_repo.insert_with_user", mock_insert),
            patch("app.services.application.async_hash_password", mock_hash),
            patch("app.services.application.emit", mock_emit),
        ):
            from app.services.application import create_application

            result = await create_application(
                guest_id=guest_id,
                username="testuser",
                password="Passw0rd!",
                display_name="Test Display",
                description="I want to join",
            )

        assert result == mock_row
        mock_emit.assert_awaited_once_with(
            "application.created",
            applicant_uid=str(guest_id),
            display_name="Test Display",
        )

    @pytest.mark.anyio
    async def test_emit_not_called_on_duplicate(self):
        """create_application does NOT emit if insert returns None (duplicate)."""
        mock_insert = AsyncMock(return_value=None)
        mock_hash = AsyncMock(return_value="hashed")
        mock_emit = AsyncMock()

        with (
            patch("app.services.application.application_repo.insert_with_user", mock_insert),
            patch("app.services.application.async_hash_password", mock_hash),
            patch("app.services.application.emit", mock_emit),
            pytest.raises(ValueError, match="pending application"),
        ):
            from app.services.application import create_application

            await create_application(
                guest_id=uuid.uuid4(),
                username="dup",
                password="Passw0rd!",
                display_name="Dup",
                description="dup",
            )

        mock_emit.assert_not_awaited()
