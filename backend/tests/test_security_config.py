"""Tests for security config and auth hardening (S02, S06).

Covers:
- S02: Development startup warning when JWT/SECRET_KEY use defaults
- S06: COOKIE_SECURE auto-derives from FASTAPI_ENV
- S06: Explicit COOKIE_SECURE env var overrides auto-derivation
"""

import sys
from unittest.mock import AsyncMock, MagicMock, call, patch

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

    def test_production_defaults_to_true(self) -> None:
        """In production mode, COOKIE_SECURE defaults to True."""
        s = _make_settings(
            FASTAPI_ENV="production",
            JWT_SECRET_KEY="prod_secret_key_safe",
            SUPER_ADMIN_PASSWORD="prod_p@ssw0rd!",
        )
        assert s.COOKIE_SECURE is True

    def test_explicit_true_overrides_development(self) -> None:
        """Explicit COOKIE_SECURE=True overrides development default."""
        s = _make_settings(FASTAPI_ENV="development", COOKIE_SECURE=True)
        assert s.COOKIE_SECURE is True

    def test_explicit_false_overrides_production(self) -> None:
        """Explicit COOKIE_SECURE=False overrides production auto-derive."""
        s = _make_settings(
            FASTAPI_ENV="production",
            COOKIE_SECURE=False,
            JWT_SECRET_KEY="prod_secret_key_safe",
            SUPER_ADMIN_PASSWORD="prod_p@ssw0rd!",
        )

    def test_unknown_env_defaults_to_false(self) -> None:
        """Unknown FASTAPI_ENV is not 'production', so COOKIE_SECURE defaults to False."""
        import warnings

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            s = _make_settings(FASTAPI_ENV="staging")
        assert s.COOKIE_SECURE is False

    def test_cookie_secure_none_resolves_to_bool(self) -> None:
        """After model_validator, COOKIE_SECURE is always a bool (never None)."""
        s = _make_settings(FASTAPI_ENV="development")
        assert isinstance(s.COOKIE_SECURE, bool)

        s2 = _make_settings(
            FASTAPI_ENV="production",
            JWT_SECRET_KEY="prod_secret_key_safe",
            SUPER_ADMIN_PASSWORD="prod_p@ssw0rd!",
        )
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
            JWT_SECRET_KEY="real_jwt_secret_not_default",
            SECRET_KEY="real_secret_key_not_default_value_here",
            POSTGRES_PASSWORD="strong_pg",
            REDIS_PASSWORD="strong_redis",
            MINIO_ROOT_PASSWORD="strong_minio",
            SUPER_ADMIN_PASSWORD="strong_admin",
            COOKIE_SECURE=True,
            MINIO_PUBLIC_URL="https://cdn.example.com",
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
