"""Tests for production secret validation in Settings (S01/S02 fix)."""

import pytest

from app.core.config import Settings


class TestProductionSecretValidation:
    # All production tests must provide all non-changeme passwords
    _SAFE_INFRA = dict(
        SECRET_KEY="real_secret_key_prod_32chars_long_ok",
        POSTGRES_PASSWORD="real_pg_password",
        REDIS_PASSWORD="real_redis_password",
        S3_SECRET_ACCESS_KEY="real_minio_password",
        S3_ACCESS_KEY_ID="prod_access_key",
        CORS_ORIGINS="https://example.com",
    )

    def test_rejects_default_jwt_secret_in_production(self):
        """Settings raises ValueError if JWT_SECRET_KEY contains 'changeme' in production."""
        with pytest.raises(ValueError, match="JWT_SECRET_KEY"):
            Settings(
                FASTAPI_ENV="production",
                JWT_SECRET_KEY="changeme_jwt_secret_key",
                SUPER_ADMIN_PASSWORD="strong_p@ssw0rd!",
                **self._SAFE_INFRA,
            )

    def test_rejects_default_admin_password_in_production(self):
        """Settings raises ValueError if SUPER_ADMIN_PASSWORD contains 'changeme' in production."""
        with pytest.raises(ValueError, match="SUPER_ADMIN_PASSWORD"):
            Settings(
                FASTAPI_ENV="production",
                JWT_SECRET_KEY="a_real_production_secret_key_here",
                SUPER_ADMIN_PASSWORD="changeme_admin",
                **self._SAFE_INFRA,
            )

    def test_rejects_both_defaults_in_production(self):
        """Settings raises ValueError when both secrets are default in production."""
        with pytest.raises(ValueError, match="JWT_SECRET_KEY"):
            Settings(
                FASTAPI_ENV="production",
                JWT_SECRET_KEY="changeme_jwt_secret_key",
                SUPER_ADMIN_PASSWORD="changeme_admin",
                **self._SAFE_INFRA,
            )

    def test_allows_defaults_in_development(self):
        """Settings allows default secrets in development mode."""
        s = Settings(
            FASTAPI_ENV="development",
            JWT_SECRET_KEY="changeme_jwt_secret_key",
            SUPER_ADMIN_PASSWORD="changeme_admin",
        )
        assert s.FASTAPI_ENV == "development"

    def test_allows_strong_secrets_in_production(self):
        """Settings allows strong secrets in production."""
        s = Settings(
            FASTAPI_ENV="production",
            JWT_SECRET_KEY="a_real_production_secret_key_here",
            SUPER_ADMIN_PASSWORD="strong_p@ssw0rd!",
            **self._SAFE_INFRA,
        )
        assert s.FASTAPI_ENV == "production"
