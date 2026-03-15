"""Tests for bootstrap_super_admin password skip optimization (Bug #15).

Verifies that:
  - When the stored password matches the .env password, no rehash occurs
  - When the stored password differs, a new hash is generated and stored
  - Create path still works normally
  - Edge case: find_by_username returns None → no update
"""

from unittest.mock import AsyncMock, patch

import pytest

from tests.conftest import make_user_dict


class TestBootstrapPasswordSkip:
    """bootstrap_super_admin should skip rehashing when password is unchanged."""

    @pytest.mark.asyncio
    async def test_skips_rehash_when_password_matches(self):
        """If async_verify_password returns True, no hash or update should occur."""
        existing_user = make_user_dict(username="admin@ai3l.community", role="SUPER_ADMIN")

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
                return_value=existing_user,
            ),
            patch(
                "app.core.security.async_verify_password",
                new_callable=AsyncMock,
                return_value=True,  # Password matches
            ) as mock_verify,
            patch(
                "app.core.security.async_hash_password",
                new_callable=AsyncMock,
                return_value="new_hashed",
            ) as mock_hash,
            patch(
                "app.repositories.user_repo.update_password_hash",
                new_callable=AsyncMock,
            ) as mock_update,
        ):
            from app.main import bootstrap_super_admin

            await bootstrap_super_admin()

            mock_verify.assert_awaited_once()
            mock_hash.assert_not_awaited()  # No rehash needed
            mock_update.assert_not_awaited()  # No DB update needed
            mock_create.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_rehashes_when_password_differs(self):
        """If async_verify_password returns False, hash and update should occur."""
        existing_user = make_user_dict(username="admin@ai3l.community", role="SUPER_ADMIN")

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
                return_value=existing_user,
            ),
            patch(
                "app.core.security.async_verify_password",
                new_callable=AsyncMock,
                return_value=False,  # Password changed
            ) as mock_verify,
            patch(
                "app.core.security.async_hash_password",
                new_callable=AsyncMock,
                return_value="new_hashed",
            ) as mock_hash,
            patch(
                "app.repositories.user_repo.update_password_hash",
                new_callable=AsyncMock,
            ) as mock_update,
        ):
            from app.main import bootstrap_super_admin

            await bootstrap_super_admin()

            mock_verify.assert_awaited_once()
            mock_hash.assert_awaited_once()
            mock_update.assert_awaited_once_with(existing_user["id"], "new_hashed")
            mock_create.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_create_path_unchanged(self):
        """When user doesn't exist, create_user is called (no verify/hash needed)."""
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
            patch(
                "app.repositories.user_repo.find_by_username",
                new_callable=AsyncMock,
            ) as mock_find,
            patch(
                "app.core.security.async_verify_password",
                new_callable=AsyncMock,
            ) as mock_verify,
            patch(
                "app.core.security.async_hash_password",
                new_callable=AsyncMock,
            ) as mock_hash,
            patch(
                "app.repositories.user_repo.update_password_hash",
                new_callable=AsyncMock,
            ) as mock_update,
        ):
            from app.main import bootstrap_super_admin

            await bootstrap_super_admin()

            mock_create.assert_awaited_once()
            mock_find.assert_not_awaited()
            mock_verify.assert_not_awaited()
            mock_hash.assert_not_awaited()
            mock_update.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_find_returns_none_skips_everything(self):
        """If user_exists is True but find_by_username returns None, no update occurs."""
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
                "app.core.security.async_verify_password",
                new_callable=AsyncMock,
            ) as mock_verify,
            patch(
                "app.core.security.async_hash_password",
                new_callable=AsyncMock,
            ) as mock_hash,
            patch(
                "app.repositories.user_repo.update_password_hash",
                new_callable=AsyncMock,
            ) as mock_update,
        ):
            from app.main import bootstrap_super_admin

            await bootstrap_super_admin()

            mock_create.assert_not_awaited()
            mock_verify.assert_not_awaited()
            mock_hash.assert_not_awaited()
            mock_update.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_verify_receives_correct_arguments(self):
        """async_verify_password should receive the .env password and stored hash."""
        existing_user = make_user_dict(username="admin@ai3l.community", role="SUPER_ADMIN")
        stored_hash = existing_user["password_hash"]

        with (
            patch(
                "app.services.user.user_exists_by_username",
                new_callable=AsyncMock,
                return_value=True,
            ),
            patch("app.services.user.create_user", new_callable=AsyncMock),
            patch(
                "app.repositories.user_repo.find_by_username",
                new_callable=AsyncMock,
                return_value=existing_user,
            ),
            patch(
                "app.core.security.async_verify_password",
                new_callable=AsyncMock,
                return_value=True,
            ) as mock_verify,
            patch("app.core.security.async_hash_password", new_callable=AsyncMock),
            patch("app.repositories.user_repo.update_password_hash", new_callable=AsyncMock),
        ):
            from app.main import bootstrap_super_admin

            await bootstrap_super_admin()

            # The .env password is passed as first arg, stored hash as second
            call_args = mock_verify.call_args[0]
            assert call_args[1] == stored_hash
