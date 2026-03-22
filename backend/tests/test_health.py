import sys
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient


def _override_auth(role="MEMBER", user_id=None):
    from app.core.deps import get_current_user
    from app.main import app

    uid = user_id or str(uuid.uuid4())
    payload = {"sub": uid, "role": role, "jti": str(uuid.uuid4())}
    app.dependency_overrides[get_current_user] = lambda: payload
    return payload, uid


def _clear_overrides():
    from app.main import app

    app.dependency_overrides.clear()


@patch("app.core.storage.get_storage")
@patch("app.api.v1.endpoints.health.get_redis")
@patch("app.api.v1.endpoints.health.get_pool")
async def test_health_check_healthy(
    mock_get_pool: MagicMock,
    mock_get_redis: MagicMock,
    mock_get_storage: MagicMock,
    client: AsyncClient,
) -> None:
    # Mock PostgreSQL
    mock_conn = AsyncMock()
    mock_conn.fetchval = AsyncMock(return_value=1)

    cm = AsyncMock()
    cm.__aenter__ = AsyncMock(return_value=mock_conn)
    cm.__aexit__ = AsyncMock(return_value=False)

    mock_pool = MagicMock()
    mock_pool.acquire.return_value = cm
    mock_get_pool.return_value = mock_pool

    # Mock Redis
    mock_redis = AsyncMock()
    mock_redis.ping = AsyncMock(return_value=True)
    mock_get_redis.return_value = mock_redis

    # Mock MinIO/Storage
    mock_s3 = MagicMock()
    mock_get_storage.return_value = mock_s3

    try:
        _override_auth("SUPER_ADMIN")
        response = await client.get(
            "/api/v1/health",
            headers={"Authorization": "Bearer fake"},
        )
    finally:
        _clear_overrides()

    assert response.status_code == 200

    data = response.json()
    assert data["status"] == "healthy"
    assert len(data["dependencies"]) == 3
    assert data["dependencies"][0]["name"] == "postgresql"
    assert data["dependencies"][1]["name"] == "redis"
    assert data["dependencies"][2]["name"] == "storage"


class TestHealthEndpointAuth:
    """M5: /health requires SUPER_ADMIN; /health/live is public."""

    @pytest.mark.anyio
    async def test_health_check_requires_super_admin(self, unauthed_client: AsyncClient) -> None:
        """GET /health without auth returns 401."""
        response = await unauthed_client.get("/api/v1/health")
        assert response.status_code == 401

    @pytest.mark.anyio
    async def test_health_check_member_rejected(self, client: AsyncClient) -> None:
        """GET /health as MEMBER returns 403."""
        try:
            _override_auth("MEMBER")
            response = await client.get(
                "/api/v1/health",
                headers={"Authorization": "Bearer fake"},
            )
        finally:
            _clear_overrides()
        assert response.status_code == 403

    @pytest.mark.anyio
    async def test_health_live_no_auth_needed(self, client: AsyncClient) -> None:
        """GET /health/live returns 200 without any auth."""
        response = await client.get("/api/v1/health/live")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"


class TestStartupSecurityChecks:
    """Unit tests for production startup security validation in main.py lifespan."""

    @pytest.mark.anyio
    async def test_startup_aborts_on_default_secret_key_in_production(self) -> None:
        """In production mode, startup must call sys.exit(1) when SECRET_KEY is default."""
        from types import SimpleNamespace
        from unittest.mock import AsyncMock, patch

        # Use SimpleNamespace to bypass Settings validator (which already blocks
        # changeme passwords in production). This test covers the lifespan layer.
        prod_settings = SimpleNamespace(
            FASTAPI_ENV="production",
            SECRET_KEY="changeme_secret_key_at_least_32_characters_long",
            POSTGRES_PASSWORD="strong_password",
            REDIS_PASSWORD="strong_redis",
            S3_SECRET_ACCESS_KEY="strong_minio",
            JWT_SECRET_KEY="strong_jwt",
            SUPER_ADMIN_PASSWORD="strong_admin",
            COOKIE_SECURE=True,
            S3_PUBLIC_URL="https://cdn.example.com",
            is_development=False,
            SENTRY_DSN="",
            DD_TRACE_ENABLED=False,
            DD_AGENT_HOST="",
            LOG_LEVEL="DEBUG",
            LOG_FORMAT="json",
            DATABASE_URL="postgresql+asyncpg://u:p@h:5432/d",
            REDIS_URL="redis://:p@h:6379/0",
            TRUSTED_HOSTS="",
        )

        exit_called_with: list[int] = []

        def fake_exit(code: int = 0) -> None:
            exit_called_with.append(code)

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
            patch.object(sys, "exit", side_effect=fake_exit),
        ):
            from app.main import app as _app
            from app.main import lifespan

            try:
                async with lifespan(_app):
                    pass
            except Exception:
                pass

        assert exit_called_with == [
            1
        ], "sys.exit(1) must be called for default SECRET_KEY in production"

    @pytest.mark.anyio
    async def test_startup_aborts_on_cookie_secure_false_in_production(self) -> None:
        """In production mode, startup must call sys.exit(1) when COOKIE_SECURE is False."""
        from unittest.mock import AsyncMock, patch

        from app.core.config import Settings

        prod_settings = Settings(
            FASTAPI_ENV="production",
            SECRET_KEY="very_strong_secret_key_for_production_use",
            POSTGRES_PASSWORD="strong_password",
            REDIS_PASSWORD="strong_redis",
            S3_SECRET_ACCESS_KEY="strong_minio",
            JWT_SECRET_KEY="strong_jwt_key_for_production",
            SUPER_ADMIN_PASSWORD="strong_admin",
            COOKIE_SECURE=False,  # insecure
        )

        exit_called_with: list[int] = []

        def fake_exit(code: int = 0) -> None:
            exit_called_with.append(code)

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
            patch.object(sys, "exit", side_effect=fake_exit),
        ):
            from app.main import app as _app
            from app.main import lifespan

            try:
                async with lifespan(_app):
                    pass
            except Exception:
                pass

        assert exit_called_with == [
            1
        ], "sys.exit(1) must be called when COOKIE_SECURE=False in production"

    @pytest.mark.anyio
    async def test_startup_succeeds_in_development_with_defaults(self) -> None:
        """In development mode, default secrets must NOT trigger sys.exit."""
        from unittest.mock import AsyncMock, patch

        from app.core.config import Settings

        dev_settings = Settings(
            FASTAPI_ENV="development",
            SECRET_KEY="changeme_secret_key_at_least_32_characters_long",
            POSTGRES_PASSWORD="changeme_postgres",
            REDIS_PASSWORD="changeme_redis",
            S3_SECRET_ACCESS_KEY="changeme_s3",
            JWT_SECRET_KEY="changeme_jwt_secret_key",
            SUPER_ADMIN_PASSWORD="changeme_admin",
            COOKIE_SECURE=False,
        )

        exit_called = False

        def fake_exit(code: int = 0) -> None:
            nonlocal exit_called
            exit_called = True

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
            patch.object(sys, "exit", side_effect=fake_exit),
        ):
            from app.main import app as _app
            from app.main import lifespan

            async with lifespan(_app):
                pass

        assert (
            not exit_called
        ), "sys.exit must NOT be called in development mode even with default secrets"
