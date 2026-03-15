"""Tests for Bug #1: audit log target_id handling for non-UUID strings."""

import uuid
from unittest.mock import patch

import pytest


class TestAuditNonUuidTargetId:
    """Verify that log_action creates an audit record even when target_id is not a valid UUID."""

    @pytest.mark.anyio
    @patch("app.repositories.audit_repo.get_pool")
    async def test_non_uuid_target_id_still_creates_record(
        self, mock_get_pool, mock_pool, mock_conn
    ):
        """A non-UUID target_id (e.g. bulk ops) should not prevent audit log creation."""
        from app.services.audit import log_action

        mock_get_pool.return_value = mock_pool

        # This is the format used by bulk role change endpoint
        non_uuid_target = "role=ADMIN,count=5"
        await log_action(
            str(uuid.uuid4()),
            "BULK_ROLE_CHANGE",
            target_type="user",
            target_id=non_uuid_target,
        )

        # The record should still be inserted (with target_id=None)
        mock_conn.execute.assert_called_once()
        call_args = mock_conn.execute.call_args[0]
        # conn.execute(SQL, log_id, user_uuid, action, target_type, target_uuid, ip_address)
        # target_uuid is at index 5
        assert call_args[5] is None  # target_uuid should be None

    @pytest.mark.anyio
    @patch("app.repositories.audit_repo.get_pool")
    async def test_comma_separated_ids_still_creates_record(
        self, mock_get_pool, mock_pool, mock_conn
    ):
        """Comma-separated post IDs (bulk delete) should not prevent audit log creation."""
        from app.services.audit import log_action

        mock_get_pool.return_value = mock_pool

        # This is the format used by bulk delete endpoint
        pid1, pid2 = uuid.uuid4(), uuid.uuid4()
        non_uuid_target = f"{pid1},{pid2}"
        await log_action(
            str(uuid.uuid4()),
            "BULK_DELETE",
            target_type="post",
            target_id=non_uuid_target,
        )

        mock_conn.execute.assert_called_once()
        call_args = mock_conn.execute.call_args[0]
        assert call_args[5] is None  # target_uuid should be None

    @pytest.mark.anyio
    @patch("app.repositories.audit_repo.get_pool")
    async def test_valid_uuid_target_id_still_works(self, mock_get_pool, mock_pool, mock_conn):
        """A valid UUID target_id should still be parsed and passed correctly."""
        from app.services.audit import log_action

        mock_get_pool.return_value = mock_pool

        target_id = str(uuid.uuid4())
        await log_action(
            str(uuid.uuid4()),
            "BAN",
            target_type="user",
            target_id=target_id,
        )

        mock_conn.execute.assert_called_once()
        call_args = mock_conn.execute.call_args[0]
        assert call_args[5] == uuid.UUID(target_id)

    @pytest.mark.anyio
    @patch("app.repositories.audit_repo.get_pool")
    async def test_none_target_id_still_works(self, mock_get_pool, mock_pool, mock_conn):
        """A None target_id should pass through as None."""
        from app.services.audit import log_action

        mock_get_pool.return_value = mock_pool

        await log_action(
            str(uuid.uuid4()),
            "LOGIN",
            target_type=None,
            target_id=None,
        )

        mock_conn.execute.assert_called_once()
        call_args = mock_conn.execute.call_args[0]
        assert call_args[5] is None

    @pytest.mark.anyio
    @patch("app.repositories.audit_repo.get_pool")
    async def test_non_uuid_target_id_logs_info(self, mock_get_pool, mock_pool, mock_conn):
        """Non-UUID target_id should log an info message with the original value."""
        from app.services.audit import log_action

        mock_get_pool.return_value = mock_pool

        with patch("app.services.audit.logger") as mock_logger:
            await log_action(
                str(uuid.uuid4()),
                "BULK_ROLE_CHANGE",
                target_type="user",
                target_id="role=ADMIN,count=5",
            )

            # Should log info about the non-UUID target_id
            mock_logger.info.assert_called_once()
            call_args = mock_logger.info.call_args
            assert "non-UUID" in call_args[0][0]

    @pytest.mark.anyio
    @patch("app.repositories.audit_repo.get_pool")
    async def test_empty_string_target_id_treated_as_falsy(
        self, mock_get_pool, mock_pool, mock_conn
    ):
        """An empty string target_id should be treated as None (falsy)."""
        from app.services.audit import log_action

        mock_get_pool.return_value = mock_pool

        await log_action(
            str(uuid.uuid4()),
            "LOGIN",
            target_type=None,
            target_id="",
        )

        mock_conn.execute.assert_called_once()
        call_args = mock_conn.execute.call_args[0]
        assert call_args[5] is None
