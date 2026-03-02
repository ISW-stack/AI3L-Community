"""Tests for bootstrap_super_admin() in app.main.

Covers:
  - Create path: user does not exist → create_user is called
  - Sync path: user already exists → password hash is updated
  - Sync path: user already exists but find_by_username returns None → no update
"""

from unittest.mock import AsyncMock, patch

from tests.conftest import make_user_dict


class TestBootstrapSuperAdmin:
    async def test_create_path_when_user_does_not_exist(self):
        """If the super admin username is not in the DB, create_user should be called."""
        mock_user = make_user_dict(username="admin@ai3l.community", role="SUPER_ADMIN")

        with (
            patch(
                "app.services.user.user_exists_by_username",
                new_callable=AsyncMock,
                return_value=False,
            ),
            patch(
                "app.services.user.create_user",
                new_callable=AsyncMock,
                return_value=mock_user,
            ) as mock_create,
            patch("app.repositories.user_repo.find_by_username", new_callable=AsyncMock),
            patch("app.repositories.user_repo.update_password_hash", new_callable=AsyncMock),
            patch("app.core.security.hash_password", return_value="hashed"),
        ):
            from app.main import bootstrap_super_admin

            await bootstrap_super_admin()

            mock_create.assert_awaited_once()
            call_kwargs = mock_create.call_args.kwargs
            assert call_kwargs["role"] == "SUPER_ADMIN"
            assert call_kwargs["display_name"] == "Super Admin"

    async def test_sync_path_when_user_already_exists(self):
        """If the super admin already exists, update_password_hash should be called."""
        existing_user = make_user_dict(username="admin@ai3l.community", role="SUPER_ADMIN")

        with (
            patch(
                "app.services.user.user_exists_by_username",
                new_callable=AsyncMock,
                return_value=True,
            ),
            patch(
                "app.services.user.create_user",
                new_callable=AsyncMock,
            ) as mock_create,
            patch(
                "app.repositories.user_repo.find_by_username",
                new_callable=AsyncMock,
                return_value=existing_user,
            ),
            patch(
                "app.repositories.user_repo.update_password_hash",
                new_callable=AsyncMock,
            ) as mock_update,
            patch("app.core.security.hash_password", return_value="new_hashed"),
        ):
            from app.main import bootstrap_super_admin

            await bootstrap_super_admin()

            mock_create.assert_not_awaited()
            mock_update.assert_awaited_once_with(existing_user["id"], "new_hashed")

    async def test_sync_path_skips_update_when_find_returns_none(self):
        """If user_exists returns True but find_by_username returns None, no update occurs."""
        with (
            patch(
                "app.services.user.user_exists_by_username",
                new_callable=AsyncMock,
                return_value=True,
            ),
            patch("app.services.user.create_user", new_callable=AsyncMock) as mock_create,
            patch(
                "app.repositories.user_repo.find_by_username",
                new_callable=AsyncMock,
                return_value=None,
            ),
            patch(
                "app.repositories.user_repo.update_password_hash",
                new_callable=AsyncMock,
            ) as mock_update,
            patch("app.core.security.hash_password", return_value="new_hashed"),
        ):
            from app.main import bootstrap_super_admin

            await bootstrap_super_admin()

            mock_create.assert_not_awaited()
            mock_update.assert_not_awaited()
