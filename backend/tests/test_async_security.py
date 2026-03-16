"""Tests for async password hashing — verifies run_in_threadpool usage."""

import uuid
from unittest.mock import AsyncMock, patch

import pytest


class TestAsyncHashPassword:
    async def test_async_hash_password_returns_string(self):
        from app.core.security import async_hash_password

        result = await async_hash_password("TestPassword1")
        assert isinstance(result, str)
        assert result.startswith("$argon2id$")

    async def test_async_hash_password_delegates_to_threadpool(self):
        """Verify async_hash_password uses run_in_threadpool (not blocking)."""
        with patch("app.core.security.run_in_threadpool", new_callable=AsyncMock) as mock_pool:
            mock_pool.return_value = "$argon2id$hashed"
            from app.core.security import async_hash_password, hash_password

            result = await async_hash_password("TestPassword1")
            mock_pool.assert_called_once_with(hash_password, "TestPassword1")
            assert result == "$argon2id$hashed"


class TestAsyncVerifyPassword:
    async def test_async_verify_password_correct(self):
        from app.core.security import async_hash_password, async_verify_password

        hashed = await async_hash_password("SecurePass1")
        assert await async_verify_password("SecurePass1", hashed) is True

    async def test_async_verify_password_wrong(self):
        from app.core.security import async_hash_password, async_verify_password

        hashed = await async_hash_password("SecurePass1")
        assert await async_verify_password("WrongPass1", hashed) is False

    async def test_async_verify_password_delegates_to_threadpool(self):
        """Verify async_verify_password uses run_in_threadpool (not blocking)."""
        with patch("app.core.security.run_in_threadpool", new_callable=AsyncMock) as mock_pool:
            mock_pool.return_value = True
            from app.core.security import async_verify_password, verify_password

            result = await async_verify_password("plain", "hashed")
            mock_pool.assert_called_once_with(verify_password, "plain", "hashed")
            assert result is True


class TestChangePasswordUsesAsync:
    @patch("app.repositories.user_repo.get_pool")
    @patch(
        "app.services.user.async_hash_password",
        new_callable=AsyncMock,
        return_value="$argon2id$new",
    )
    @patch(
        "app.services.user.async_verify_password",
        new_callable=AsyncMock,
        return_value=True,
    )
    @patch("app.services.user.user_repo")
    async def test_change_password_uses_async_functions(
        self, mock_repo, mock_verify, mock_hash, mock_get_pool
    ):
        """change_password must use async_verify_password and async_hash_password."""
        import uuid

        from app.services.user import change_password

        user_id = uuid.uuid4()
        mock_repo.find_password_hash = AsyncMock(return_value="$argon2id$old")
        mock_repo.update_password_hash = AsyncMock()

        result = await change_password(user_id, "OldPass123!", "NewPass123!")
        assert result is True
        mock_verify.assert_called_once_with("OldPass123!", "$argon2id$old")
        mock_hash.assert_called_once_with("NewPass123!")

    @patch("app.services.user.user_repo")
    @patch(
        "app.services.user.async_verify_password",
        new_callable=AsyncMock,
        return_value=False,
    )
    async def test_change_password_wrong_old_password(self, mock_verify, mock_repo):
        import uuid

        from app.services.user import change_password

        mock_repo.find_password_hash = AsyncMock(return_value="$argon2id$old")

        with pytest.raises(ValueError, match="Current password is incorrect"):
            await change_password(uuid.uuid4(), "WrongPass1", "NewPass123")


class TestRegisterUsesAsync:
    @patch("app.core.database.get_pool")
    @patch(
        "app.core.security.async_hash_password",
        new_callable=AsyncMock,
        return_value="$argon2id$hashed",
    )
    async def test_register_uses_async_hash(self, mock_hash, mock_get_pool, mock_pool, mock_conn):
        from app.services.auth import register_new_user

        mock_conn.fetchrow.return_value = {
            "id": "user-1",
            "username": "newuser",
            "role": "MEMBER",
        }
        mock_conn.execute.return_value = "UPDATE 1"
        mock_get_pool.return_value = mock_pool

        result = await register_new_user("newuser", "Password1", "New User", "INV-CODE")
        mock_hash.assert_called_once_with("Password1")
        assert result["username"] == "newuser"


class TestFileUploadUsesThreadpool:
    @patch("app.api.v1.endpoints.files.file_scan_repo")
    @patch("app.api.v1.endpoints.files.async_upload_file", new_callable=AsyncMock)
    @patch(
        "app.api.v1.endpoints.files.user_repo.increment_storage_used",
        new_callable=AsyncMock,
    )
    @patch(
        "app.api.v1.endpoints.files.user_repo.get_storage_used",
        new_callable=AsyncMock,
        return_value=0,
    )
    @patch("app.api.v1.endpoints.files.get_redis")
    @patch("app.api.v1.endpoints.files.check_rate_limit", new_callable=AsyncMock, return_value=True)
    @patch("app.api.v1.endpoints.files.run_in_threadpool", new_callable=AsyncMock)
    async def test_validate_editor_file_called_via_threadpool(
        self,
        mock_threadpool,
        mock_rate_limit,
        mock_get_redis,
        mock_storage_used,
        mock_increment,
        mock_upload,
        mock_scan_repo,
        client,
    ):
        """validate_editor_file must be called through run_in_threadpool."""
        from app.core.deps import get_current_user
        from app.main import app

        # Mock threadpool to return valid result
        mock_threadpool.return_value = ("image/png", b"\x89PNG" + b"\x00" * 100)

        redis = AsyncMock()
        redis.set = AsyncMock(return_value=True)
        redis.delete = AsyncMock()
        mock_get_redis.return_value = redis
        mock_scan_repo.insert = AsyncMock()

        payload = {"sub": str(uuid.uuid4()), "role": "MEMBER", "jti": "test"}
        app.dependency_overrides[get_current_user] = lambda: payload

        try:
            from io import BytesIO

            png_data = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
            await client.post(
                "/api/v1/files/upload/editor",
                files={"file": ("test.png", BytesIO(png_data), "image/png")},
                headers={"Authorization": "Bearer fake"},
            )
            # Verify run_in_threadpool was called (for validate_editor_file)
            assert mock_threadpool.call_count >= 1
            # First call should be validate_editor_file
            first_call = mock_threadpool.call_args_list[0]
            from app.core.file_validation import validate_editor_file

            assert first_call[0][0] is validate_editor_file
        finally:
            app.dependency_overrides.pop(get_current_user, None)
