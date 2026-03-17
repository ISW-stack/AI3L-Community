"""Tests for role protection: last SUPER_ADMIN cannot be demoted."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

_DB = "app.core.database"
_REPO = "app.services.user.user_repo"


class TestLastSuperAdminProtection:
    @pytest.mark.anyio
    async def test_demote_last_super_admin_raises(self, mock_pool, mock_conn):
        """update_user_role raises ValueError when demoting the last SUPER_ADMIN."""
        from app.services.user import update_user_role

        user_id = uuid.uuid4()

        # count_super_admins_for_update returns 1 (last SA)
        # fetchrow for the user returns SUPER_ADMIN role
        mock_conn.fetchval = AsyncMock(return_value=1)
        mock_conn.fetchrow = AsyncMock(return_value={"role": "SUPER_ADMIN"})

        with patch(f"{_DB}.get_pool", return_value=mock_pool):
            with pytest.raises(ValueError, match="last Super Admin"):
                await update_user_role(user_id, "ADMIN")

    @pytest.mark.anyio
    async def test_demote_super_admin_when_others_exist(self, mock_pool, mock_conn):
        """update_user_role succeeds when there are multiple SUPER_ADMINs."""
        from app.services.user import update_user_role

        user_id = uuid.uuid4()
        updated_row = {"id": user_id, "role": "ADMIN"}

        # count_super_admins_for_update returns 2 (multiple SAs)
        mock_conn.fetchval = AsyncMock(return_value=2)
        # First fetchrow: current user role check; second: update_role_in_conn RETURNING
        mock_conn.fetchrow = AsyncMock(side_effect=[
            {"role": "SUPER_ADMIN"},
            updated_row,
        ])

        with patch(f"{_DB}.get_pool", return_value=mock_pool):
            result = await update_user_role(user_id, "ADMIN")
        assert result is not None
        assert result["role"] == "ADMIN"

    @pytest.mark.anyio
    async def test_promote_to_super_admin_always_allowed(self, mock_pool, mock_conn):
        """update_user_role to SUPER_ADMIN should never be blocked."""
        from app.services.user import update_user_role

        user_id = uuid.uuid4()
        updated_row = {"id": user_id, "role": "SUPER_ADMIN"}

        # For promotion, the SA check is skipped entirely
        mock_conn.fetchrow = AsyncMock(return_value=updated_row)

        with patch(f"{_DB}.get_pool", return_value=mock_pool):
            result = await update_user_role(user_id, "SUPER_ADMIN")
        assert result is not None

        # fetchval should not have been called (no count check for promotion)
        mock_conn.fetchval.assert_not_called()

    @pytest.mark.anyio
    async def test_demote_non_super_admin_skips_check(self, mock_pool, mock_conn):
        """update_user_role from ADMIN to MEMBER skips SUPER_ADMIN count block."""
        from app.services.user import update_user_role

        user_id = uuid.uuid4()
        updated_row = {"id": user_id, "role": "MEMBER"}

        # count_super_admins_for_update returns 1 but user is ADMIN, not SA
        mock_conn.fetchval = AsyncMock(return_value=1)
        # First fetchrow: current user is ADMIN; second: update_role_in_conn RETURNING
        mock_conn.fetchrow = AsyncMock(side_effect=[
            {"role": "ADMIN"},
            updated_row,
        ])

        with patch(f"{_DB}.get_pool", return_value=mock_pool):
            result = await update_user_role(user_id, "MEMBER")
        assert result is not None

    @pytest.mark.anyio
    async def test_concurrent_demote_protection(self, mock_pool, mock_conn):
        """Verify FOR UPDATE lock is used in the count query to prevent TOCTOU."""
        from app.services.user import update_user_role

        user_id = uuid.uuid4()

        # 2 SAs so the demote is allowed — we just want to verify the query text
        mock_conn.fetchval = AsyncMock(return_value=2)
        mock_conn.fetchrow = AsyncMock(side_effect=[
            {"role": "SUPER_ADMIN"},
            {"id": user_id, "role": "ADMIN"},
        ])

        with patch(f"{_DB}.get_pool", return_value=mock_pool):
            await update_user_role(user_id, "ADMIN")

        # Verify transaction was used
        mock_conn.transaction.assert_called_once()

        # Verify FOR UPDATE was used in the count query
        fetchval_call = mock_conn.fetchval.call_args
        assert "FOR UPDATE" in fetchval_call[0][0]

        # Verify FOR UPDATE was used in the user row lock query
        first_fetchrow_call = mock_conn.fetchrow.call_args_list[0]
        assert "FOR UPDATE" in first_fetchrow_call[0][0]
