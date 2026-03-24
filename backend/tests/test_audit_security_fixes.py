"""Tests for pre-deployment audit security fixes.

Covers: DB-19, AUTH-01, API-01, API-37, INFRA-20, INFRA-24.
"""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestDB19ReportStatusFilter:
    """DB-19: _VALID_REPORT_STATUSES must include RESOLVED (not REVIEWED)."""

    def test_resolved_in_valid_statuses(self):
        from app.repositories.report_repo import _VALID_REPORT_STATUSES

        assert "RESOLVED" in _VALID_REPORT_STATUSES
        assert "REVIEWED" not in _VALID_REPORT_STATUSES

    def test_valid_statuses_are_correct(self):
        from app.repositories.report_repo import _VALID_REPORT_STATUSES

        assert _VALID_REPORT_STATUSES == {"PENDING", "RESOLVED", "DISMISSED"}

    @pytest.mark.anyio
    async def test_find_many_applies_resolved_filter(self, mock_pool, mock_conn):
        """Filtering by RESOLVED should apply the WHERE clause, not silently drop it."""
        from unittest.mock import PropertyMock

        row_data = {
            "id": uuid.uuid4(),
            "post_id": uuid.uuid4(),
            "user_id": uuid.uuid4(),
            "reason": "test",
            "status": "RESOLVED",
            "post_title": "Test Post",
            "_total": 1,
            "created_at": "2026-01-01",
            "reviewed_by": None,
            "reviewed_at": None,
            "updated_at": None,
        }
        # Create a mock that behaves like an asyncpg Record (supports dict-like access)
        mock_row = MagicMock()
        mock_row.__getitem__ = MagicMock(side_effect=row_data.__getitem__)
        mock_row.items = MagicMock(return_value=row_data.items())
        mock_conn.fetch.return_value = [mock_row]

        with patch("app.repositories.report_repo.get_pool", return_value=mock_pool):
            from app.repositories.report_repo import find_many

            results, total = await find_many(status_filter="RESOLVED")

        # Verify the query included a WHERE clause with RESOLVED
        call_args = mock_conn.fetch.call_args
        query = call_args[0][0]
        assert "WHERE pr.status = $1" in query
        assert call_args[0][1] == "RESOLVED"


class TestAUTH01TimingOracle:
    """AUTH-01: authenticate_user must call verify_password even for non-existent users."""

    @pytest.mark.anyio
    async def test_nonexistent_user_calls_verify(self):
        """Non-existent user must still call async_verify_password to prevent timing oracle."""
        with (
            patch(
                "app.services.auth.get_user_by_username",
                new_callable=AsyncMock,
                return_value=None,
            ),
            patch(
                "app.services.auth.async_verify_password",
                new_callable=AsyncMock,
                return_value=False,
            ) as mock_verify,
        ):
            from app.services.auth import authenticate_user

            result = await authenticate_user("nonexistent", "password123")

            assert result is None
            mock_verify.assert_awaited_once()

    @pytest.mark.anyio
    async def test_deleted_user_calls_verify(self):
        """Deleted user must still call async_verify_password."""
        from tests.conftest import make_user_dict

        deleted_user = make_user_dict(is_deleted=True)

        with (
            patch(
                "app.services.auth.get_user_by_username",
                new_callable=AsyncMock,
                return_value=deleted_user,
            ),
            patch(
                "app.services.auth.async_verify_password",
                new_callable=AsyncMock,
                return_value=False,
            ) as mock_verify,
        ):
            from app.services.auth import authenticate_user

            result = await authenticate_user("deleteduser", "password123")

            assert result is None
            mock_verify.assert_awaited_once()

    def test_dummy_hash_is_valid_argon2(self):
        """The _DUMMY_HASH should be a valid Argon2 hash string."""
        from app.services.auth import _DUMMY_HASH

        assert _DUMMY_HASH.startswith("$argon2id$")
        assert len(_DUMMY_HASH) > 50


class TestAPI01LoginMinLength:
    """API-01: LoginRequest.username and password must have min_length=1."""

    @pytest.mark.anyio
    async def test_empty_username_rejected(self, client):
        """Empty username should return 422."""
        with patch(
            "app.api.v1.endpoints.auth.check_rate_limit",
            new_callable=AsyncMock,
            return_value=True,
        ):
            resp = await client.post(
                "/api/v1/auth/login",
                json={
                    "username": "",
                    "password": "test123",
                    "captcha_id": "x",
                    "captcha_code": "1234",
                },
            )
            assert resp.status_code == 422

    @pytest.mark.anyio
    async def test_empty_password_rejected(self, client):
        """Empty password should return 422."""
        with patch(
            "app.api.v1.endpoints.auth.check_rate_limit",
            new_callable=AsyncMock,
            return_value=True,
        ):
            resp = await client.post(
                "/api/v1/auth/login",
                json={
                    "username": "testuser",
                    "password": "",
                    "captcha_id": "x",
                    "captcha_code": "1234",
                },
            )
            assert resp.status_code == 422


class TestAPI37SigPostsRequireMember:
    """API-37: get_sig_posts must require MEMBER+ role."""

    @pytest.mark.anyio
    async def test_guest_cannot_access_sig_posts(self, client):
        """A GUEST user should get 403 when accessing SIG posts."""
        from app.core.deps import get_current_user
        from app.main import app

        guest_payload = {
            "sub": str(uuid.uuid4()),
            "role": "GUEST",
            "jti": str(uuid.uuid4()),
        }
        app.dependency_overrides[get_current_user] = lambda: guest_payload

        try:
            resp = await client.get(f"/api/v1/sigs/{uuid.uuid4()}/posts")
            assert resp.status_code == 403
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.anyio
    async def test_member_can_access_sig_posts(self, client):
        """A MEMBER user should be allowed to access SIG posts."""
        from app.core.deps import get_current_user
        from app.main import app

        member_payload = {
            "sub": str(uuid.uuid4()),
            "role": "MEMBER",
            "jti": str(uuid.uuid4()),
        }
        app.dependency_overrides[get_current_user] = lambda: member_payload

        try:
            with patch(
                "app.api.v1.endpoints.sigs.list_posts",
                new_callable=AsyncMock,
                return_value={"posts": [], "total": 0, "total_pages": 0},
            ):
                resp = await client.get(f"/api/v1/sigs/{uuid.uuid4()}/posts")
                assert resp.status_code == 200
        finally:
            app.dependency_overrides.clear()


class TestINFRA20MinioCredentials:
    """INFRA-20: Production must reject default MinIO credentials."""

    def test_minioadmin_rejected_in_production(self):
        """S3_ACCESS_KEY_ID='minioadmin' should be rejected in production."""
        import os

        env_overrides = {
            "FASTAPI_ENV": "production",
            "JWT_SECRET_KEY": "a" * 32,
            "SECRET_KEY": "b" * 32,
            "SUPER_ADMIN_PASSWORD": "StrongPass!1",
            "POSTGRES_PASSWORD": "pg_secure_123",
            "REDIS_PASSWORD": "redis_secure_123",
            "S3_SECRET_ACCESS_KEY": "s3_secure_key_123",
            "S3_ACCESS_KEY_ID": "minioadmin",
            "CORS_ORIGINS": "https://example.com",
            "COOKIE_DOMAIN": "example.com",
        }
        with patch.dict(os.environ, env_overrides, clear=False):
            with pytest.raises(ValueError, match="minioadmin"):
                from app.core.config import Settings

                Settings()


class TestINFRA24CorsOrigins:
    """INFRA-24: Production must reject CORS_ORIGINS containing localhost."""

    def test_localhost_cors_rejected_in_production(self):
        """CORS_ORIGINS with localhost should be rejected in production."""
        import os

        env_overrides = {
            "FASTAPI_ENV": "production",
            "JWT_SECRET_KEY": "a" * 32,
            "SECRET_KEY": "b" * 32,
            "SUPER_ADMIN_PASSWORD": "StrongPass!1",
            "POSTGRES_PASSWORD": "pg_secure_123",
            "REDIS_PASSWORD": "redis_secure_123",
            "S3_SECRET_ACCESS_KEY": "s3_secure_key_123",
            "S3_ACCESS_KEY_ID": "prod_access_key",
            "CORS_ORIGINS": "http://localhost:3000",
            "COOKIE_DOMAIN": "example.com",
        }
        with patch.dict(os.environ, env_overrides, clear=False):
            with pytest.raises(ValueError, match="localhost"):
                from app.core.config import Settings

                Settings()
