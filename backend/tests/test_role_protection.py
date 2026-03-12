"""Tests for role protection: last SUPER_ADMIN cannot be demoted."""

import uuid
from unittest.mock import AsyncMock, patch

import pytest

_SVC = "app.services.user"


class TestLastSuperAdminProtection:
    @pytest.mark.anyio
    async def test_demote_last_super_admin_raises(self, mock_pool, mock_conn):
        """update_user_role raises ValueError when demoting the last SUPER_ADMIN."""
        from app.services.user import update_user_role

        user_id = uuid.uuid4()

        with (
            patch(
                f"{_SVC}.user_repo.find_by_id",
                new_callable=AsyncMock,
                return_value={"role": "SUPER_ADMIN"},
            ),
            patch(
                f"{_SVC}.user_repo.count_by_role",
                new_callable=AsyncMock,
                return_value=1,
            ),
        ):
            with pytest.raises(ValueError, match="last Super Admin"):
                await update_user_role(user_id, "ADMIN")

    @pytest.mark.anyio
    async def test_demote_super_admin_when_others_exist(
        self, mock_pool, mock_conn
    ):
        """update_user_role succeeds when there are multiple SUPER_ADMINs."""
        from app.services.user import update_user_role

        user_id = uuid.uuid4()

        with (
            patch(
                f"{_SVC}.user_repo.find_by_id",
                new_callable=AsyncMock,
                return_value={"role": "SUPER_ADMIN"},
            ),
            patch(
                f"{_SVC}.user_repo.count_by_role",
                new_callable=AsyncMock,
                return_value=2,
            ),
            patch(
                f"{_SVC}.user_repo.update_role",
                new_callable=AsyncMock,
                return_value={"id": user_id, "role": "ADMIN"},
            ),
        ):
            result = await update_user_role(user_id, "ADMIN")
        assert result is not None
        assert result["role"] == "ADMIN"

    @pytest.mark.anyio
    async def test_promote_to_super_admin_always_allowed(
        self, mock_pool, mock_conn
    ):
        """update_user_role to SUPER_ADMIN should never be blocked."""
        from app.services.user import update_user_role

        user_id = uuid.uuid4()

        with patch(
            f"{_SVC}.user_repo.update_role",
            new_callable=AsyncMock,
            return_value={"id": user_id, "role": "SUPER_ADMIN"},
        ):
            result = await update_user_role(user_id, "SUPER_ADMIN")
        assert result is not None

    @pytest.mark.anyio
    async def test_demote_non_super_admin_skips_check(
        self, mock_pool, mock_conn
    ):
        """update_user_role from ADMIN to MEMBER skips SUPER_ADMIN check."""
        from app.services.user import update_user_role

        user_id = uuid.uuid4()

        with (
            patch(
                f"{_SVC}.user_repo.find_by_id",
                new_callable=AsyncMock,
                return_value={"role": "ADMIN"},
            ),
            patch(
                f"{_SVC}.user_repo.update_role",
                new_callable=AsyncMock,
                return_value={"id": user_id, "role": "MEMBER"},
            ),
        ):
            result = await update_user_role(user_id, "MEMBER")
        assert result is not None
