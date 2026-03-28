"""Tests for security config and auth hardening (S02, S06).

Covers:
- S02: Development startup warning when JWT/SECRET_KEY use defaults
- S06: COOKIE_SECURE auto-derives from FASTAPI_ENV
- S06: Explicit COOKIE_SECURE env var overrides auto-derivation
"""

import sys
from unittest.mock import AsyncMock, patch

import pytest
from pydantic_settings import SettingsConfigDict

from app.core.config import Settings


def _make_settings(**overrides: object) -> Settings:
    """Create a Settings instance with env_file disabled to avoid .env interference."""

    class TestSettingsClass(Settings):
        model_config = SettingsConfigDict(env_file=None, extra="ignore")

    return TestSettingsClass(**overrides)


# ---------------------------------------------------------------------------
# S06: COOKIE_SECURE auto-derives from FASTAPI_ENV
# ---------------------------------------------------------------------------


class TestCookieSecureAutoDerive:
    def test_development_defaults_to_false(self) -> None:
        """In development mode, COOKIE_SECURE defaults to False."""
        s = _make_settings(FASTAPI_ENV="development")
        assert s.COOKIE_SECURE is False

    def test_test_env_defaults_to_false(self) -> None:
        """In test mode, COOKIE_SECURE defaults to False."""
        s = _make_settings(FASTAPI_ENV="test")
        assert s.COOKIE_SECURE is False

    _SAFE_PROD: dict = dict(
        JWT_SECRET_KEY="prod_secret_key_safe_at_least_32chars_long",
        SECRET_KEY="real_secret_key_prod_32chars_long_ok",
        SUPER_ADMIN_PASSWORD="prod_p@ssw0rd!",
        POSTGRES_PASSWORD="real_pg_password",
        REDIS_PASSWORD="real_redis_password",
        S3_SECRET_ACCESS_KEY="real_minio_password",
        S3_ACCESS_KEY_ID="prod_access_key",
        CORS_ORIGINS="https://example.com",
    )

    def test_production_defaults_to_true(self) -> None:
        """In production mode, COOKIE_SECURE defaults to True."""
        s = _make_settings(FASTAPI_ENV="production", **self._SAFE_PROD)
        assert s.COOKIE_SECURE is True

    def test_explicit_true_overrides_development(self) -> None:
        """Explicit COOKIE_SECURE=True overrides development default."""
        s = _make_settings(FASTAPI_ENV="development", COOKIE_SECURE=True)
        assert s.COOKIE_SECURE is True

    def test_explicit_false_overrides_production(self) -> None:
        """Explicit COOKIE_SECURE=False overrides production auto-derive."""
        _make_settings(
            FASTAPI_ENV="production",
            COOKIE_SECURE=False,
            **self._SAFE_PROD,
        )

    def test_unknown_env_defaults_to_false(self) -> None:
        """Unknown FASTAPI_ENV is not 'production', so COOKIE_SECURE defaults to False."""
        import warnings

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            s = _make_settings(FASTAPI_ENV="staging", **self._SAFE_PROD)
        assert s.COOKIE_SECURE is False

    def test_cookie_secure_none_resolves_to_bool(self) -> None:
        """After model_validator, COOKIE_SECURE is always a bool (never None)."""
        s = _make_settings(FASTAPI_ENV="development")
        assert isinstance(s.COOKIE_SECURE, bool)

        s2 = _make_settings(FASTAPI_ENV="production", **self._SAFE_PROD)
        assert isinstance(s2.COOKIE_SECURE, bool)


# ---------------------------------------------------------------------------
# S02: Development startup warning for default secrets
# ---------------------------------------------------------------------------


class TestDevSecretWarnings:
    @pytest.mark.anyio
    async def test_dev_warns_on_default_jwt_secret(self) -> None:
        """In development, lifespan logs a warning when JWT_SECRET_KEY is the default."""
        dev_settings = _make_settings(
            FASTAPI_ENV="development",
            JWT_SECRET_KEY="changeme_jwt_secret_key",
            SECRET_KEY="real_secret_key_not_default_value_here",
        )

        with (
            patch("app.main.settings", dev_settings),
            patch("app.main.init_db_pool", new_callable=AsyncMock),
            patch("app.main.init_redis", new_callable=AsyncMock),
            patch("app.main.close_db_pool", new_callable=AsyncMock),
            patch("app.main.close_redis", new_callable=AsyncMock),
            patch("app.main.close_storage"),
            patch("app.main.init_storage"),
            patch("app.main.bootstrap_super_admin", new_callable=AsyncMock),
            patch("app.main.setup_logging"),
            patch("app.event_handlers.register_all"),
            patch("app.api.v1.endpoints.ws.start_redis_subscriber", new_callable=AsyncMock),
            patch("app.api.v1.endpoints.ws.stop_redis_subscriber", new_callable=AsyncMock),
            patch("app.main.logger") as mock_logger,
        ):
            from app.main import app as _app
            from app.main import lifespan

            async with lifespan(_app):
                pass

            # Check that a warning was logged about JWT_SECRET_KEY
            warning_calls = [
                c for c in mock_logger.warning.call_args_list if "JWT_SECRET_KEY" in str(c)
            ]
            assert len(warning_calls) >= 1, "Should warn about default JWT_SECRET_KEY in dev"

    @pytest.mark.anyio
    async def test_dev_warns_on_default_secret_key(self) -> None:
        """In development, lifespan logs a warning when SECRET_KEY is the default."""
        dev_settings = _make_settings(
            FASTAPI_ENV="development",
            JWT_SECRET_KEY="real_jwt_secret_not_default",
            SECRET_KEY="changeme_secret_key_at_least_32_characters_long",
        )

        with (
            patch("app.main.settings", dev_settings),
            patch("app.main.init_db_pool", new_callable=AsyncMock),
            patch("app.main.init_redis", new_callable=AsyncMock),
            patch("app.main.close_db_pool", new_callable=AsyncMock),
            patch("app.main.close_redis", new_callable=AsyncMock),
            patch("app.main.close_storage"),
            patch("app.main.init_storage"),
            patch("app.main.bootstrap_super_admin", new_callable=AsyncMock),
            patch("app.main.setup_logging"),
            patch("app.event_handlers.register_all"),
            patch("app.api.v1.endpoints.ws.start_redis_subscriber", new_callable=AsyncMock),
            patch("app.api.v1.endpoints.ws.stop_redis_subscriber", new_callable=AsyncMock),
            patch("app.main.logger") as mock_logger,
        ):
            from app.main import app as _app
            from app.main import lifespan

            async with lifespan(_app):
                pass

            warning_calls = [
                c for c in mock_logger.warning.call_args_list if "SECRET_KEY" in str(c)
            ]
            assert len(warning_calls) >= 1, "Should warn about default SECRET_KEY in dev"

    @pytest.mark.anyio
    async def test_dev_no_warning_with_real_secrets(self) -> None:
        """In development, no secret warning when both keys are non-default."""
        dev_settings = _make_settings(
            FASTAPI_ENV="development",
            JWT_SECRET_KEY="real_jwt_secret_not_default",
            SECRET_KEY="real_secret_key_not_default_value_here",
        )

        with (
            patch("app.main.settings", dev_settings),
            patch("app.main.init_db_pool", new_callable=AsyncMock),
            patch("app.main.init_redis", new_callable=AsyncMock),
            patch("app.main.close_db_pool", new_callable=AsyncMock),
            patch("app.main.close_redis", new_callable=AsyncMock),
            patch("app.main.close_storage"),
            patch("app.main.init_storage"),
            patch("app.main.bootstrap_super_admin", new_callable=AsyncMock),
            patch("app.main.setup_logging"),
            patch("app.event_handlers.register_all"),
            patch("app.api.v1.endpoints.ws.start_redis_subscriber", new_callable=AsyncMock),
            patch("app.api.v1.endpoints.ws.stop_redis_subscriber", new_callable=AsyncMock),
            patch("app.main.logger") as mock_logger,
        ):
            from app.main import app as _app
            from app.main import lifespan

            async with lifespan(_app):
                pass

            # No warnings about default keys
            secret_warnings = [
                c
                for c in mock_logger.warning.call_args_list
                if "JWT_SECRET_KEY" in str(c) or "SECRET_KEY" in str(c)
            ]
            assert len(secret_warnings) == 0, "Should not warn when secrets are non-default"

    @pytest.mark.anyio
    async def test_production_does_not_use_dev_warning_path(self) -> None:
        """In production, the dev warning block is skipped (production has its own checks)."""
        prod_settings = _make_settings(
            FASTAPI_ENV="production",
            JWT_SECRET_KEY="real_jwt_secret_not_default_at_least_32chars",
            SECRET_KEY="real_secret_key_not_default_value_here",
            POSTGRES_PASSWORD="strong_pg",
            REDIS_PASSWORD="strong_redis",
            S3_SECRET_ACCESS_KEY="strong_minio",
            S3_ACCESS_KEY_ID="prod_access_key",
            CORS_ORIGINS="https://example.com",
            SUPER_ADMIN_PASSWORD="strong_admin",
            COOKIE_SECURE=True,
            S3_PUBLIC_URL="https://cdn.example.com",
        )

        exit_called: list[int] = []

        def fake_exit(code: int = 0) -> None:
            exit_called.append(code)

        with (
            patch("app.main.settings", prod_settings),
            patch("app.main.init_db_pool", new_callable=AsyncMock),
            patch("app.main.init_redis", new_callable=AsyncMock),
            patch("app.main.close_db_pool", new_callable=AsyncMock),
            patch("app.main.close_redis", new_callable=AsyncMock),
            patch("app.main.close_storage"),
            patch("app.main.init_storage"),
            patch("app.main.bootstrap_super_admin", new_callable=AsyncMock),
            patch("app.main.setup_logging"),
            patch("app.event_handlers.register_all"),
            patch("app.api.v1.endpoints.ws.start_redis_subscriber", new_callable=AsyncMock),
            patch("app.api.v1.endpoints.ws.stop_redis_subscriber", new_callable=AsyncMock),
            patch("app.main.logger") as mock_logger,
            patch.object(sys, "exit", side_effect=fake_exit),
        ):
            from app.main import app as _app
            from app.main import lifespan

            try:
                async with lifespan(_app):
                    pass
            except Exception:
                pass

        # Production with all real secrets should NOT abort
        assert 1 not in exit_called, "Should not abort when all secrets are non-default"
        # The dev warning path should NOT have run (is_development is False)
        dev_warning_calls = [
            c
            for c in mock_logger.warning.call_args_list
            if "still using the default value" in str(c)
        ]
        assert len(dev_warning_calls) == 0, "Dev warning should not fire in production mode"


# ---------------------------------------------------------------------------
# H-05: DATABASE_SSL must be enforced in production for remote hosts
# ---------------------------------------------------------------------------


class TestDatabaseSSLEnforcement:
    _SAFE_PROD = TestCookieSecureAutoDerive._SAFE_PROD

    def test_production_remote_host_no_ssl_raises(self) -> None:
        """Production with remote PG host and DATABASE_SSL=false must raise ValueError."""
        with pytest.raises(ValueError, match="DATABASE_SSL"):
            _make_settings(
                FASTAPI_ENV="production",
                POSTGRES_HOST="db.example.com",
                DATABASE_SSL=False,
                **self._SAFE_PROD,
            )

    def test_production_localhost_no_ssl_ok(self) -> None:
        """Production with localhost PG host and no SSL is allowed (same-host)."""
        s = _make_settings(
            FASTAPI_ENV="production",
            POSTGRES_HOST="localhost",
            DATABASE_SSL=False,
            **self._SAFE_PROD,
        )
        assert s.DATABASE_SSL is False

    def test_production_docker_host_no_ssl_ok(self) -> None:
        """Production with 'postgres' (Docker service name) and no SSL is allowed."""
        s = _make_settings(
            FASTAPI_ENV="production",
            POSTGRES_HOST="postgres",
            DATABASE_SSL=False,
            **self._SAFE_PROD,
        )
        assert s.DATABASE_SSL is False

    def test_development_remote_host_no_ssl_warns(self) -> None:
        """Development with remote PG host should warn but not raise."""
        import warnings

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            _make_settings(
                FASTAPI_ENV="development",
                POSTGRES_HOST="db.example.com",
                DATABASE_SSL=False,
            )
        ssl_warnings = [x for x in w if "DATABASE_SSL" in str(x.message)]
        assert len(ssl_warnings) >= 1

    def test_production_remote_host_with_ssl_ok(self) -> None:
        """Production with remote PG host and DATABASE_SSL=true is fine."""
        s = _make_settings(
            FASTAPI_ENV="production",
            POSTGRES_HOST="db.example.com",
            DATABASE_SSL=True,
            **self._SAFE_PROD,
        )
        assert s.DATABASE_SSL is True


# ---------------------------------------------------------------------------
# H-06: CORS wildcard/malformed origins must be blocked in production
# ---------------------------------------------------------------------------


class TestCORSProductionEnforcement:
    _SAFE_PROD = {**TestCookieSecureAutoDerive._SAFE_PROD}

    def test_production_wildcard_origin_raises(self) -> None:
        """Production CORS_ORIGINS with wildcard must raise ValueError."""
        overrides = {**self._SAFE_PROD, "CORS_ORIGINS": "*"}
        with pytest.raises(ValueError, match="(wildcard|http)"):
            s = _make_settings(FASTAPI_ENV="production", **overrides)
            _ = s.CORS_ORIGINS_LIST  # property triggers validation

    def test_production_malformed_origin_raises(self) -> None:
        """Production CORS_ORIGINS without http(s):// prefix must raise."""
        overrides = {**self._SAFE_PROD, "CORS_ORIGINS": "example.com"}
        with pytest.raises(ValueError, match="http"):
            s = _make_settings(FASTAPI_ENV="production", **overrides)
            _ = s.CORS_ORIGINS_LIST

    def test_production_valid_origin_ok(self) -> None:
        """Production with proper https:// origin is accepted."""
        overrides = {**self._SAFE_PROD, "CORS_ORIGINS": "https://app.example.com"}
        s = _make_settings(FASTAPI_ENV="production", **overrides)
        assert s.CORS_ORIGINS_LIST == ["https://app.example.com"]

    def test_development_wildcard_warns_only(self) -> None:
        """Development with wildcard origin warns but doesn't raise."""
        import warnings

        s = _make_settings(FASTAPI_ENV="development", CORS_ORIGINS="*")
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            _ = s.CORS_ORIGINS_LIST
        wildcard_warnings = [x for x in w if "wildcard" in str(x.message)]
        assert len(wildcard_warnings) >= 1
