"""Tests for backend core modules: config, rate_limit, database."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# config.py
# ---------------------------------------------------------------------------

class TestSettings:
    """Test Settings class default values and computed properties."""

    def _make_settings(self, **overrides):
        """Create a Settings instance with env_file disabled to avoid .env interference."""
        from pydantic_settings import SettingsConfigDict

        from app.core.config import Settings

        # Subclass to disable env_file loading so tests use only defaults + overrides
        class TestSettingsClass(Settings):
            model_config = SettingsConfigDict(env_file=None, extra="ignore")

        return TestSettingsClass(**overrides)

    # -- Default values --

    def test_default_fastapi_env(self):
        s = self._make_settings()
        assert s.FASTAPI_ENV == "development"

    def test_default_fastapi_debug_false(self):
        s = self._make_settings()
        assert s.FASTAPI_DEBUG is False

    def test_default_fastapi_host(self):
        s = self._make_settings()
        assert s.FASTAPI_HOST == "0.0.0.0"

    def test_default_fastapi_port(self):
        s = self._make_settings()
        assert s.FASTAPI_PORT == 8000

    def test_default_fastapi_workers(self):
        s = self._make_settings()
        assert s.FASTAPI_WORKERS == 1

    def test_default_postgres_port(self):
        s = self._make_settings()
        assert s.POSTGRES_PORT == 5432

    def test_default_redis_port(self):
        s = self._make_settings()
        assert s.REDIS_PORT == 6379

    def test_default_jwt_algorithm(self):
        s = self._make_settings()
        assert s.JWT_ALGORITHM == "HS256"

    def test_default_jwt_guest_expire(self):
        s = self._make_settings()
        assert s.JWT_GUEST_EXPIRE_MINUTES == 45

    def test_default_jwt_member_expire(self):
        s = self._make_settings()
        assert s.JWT_MEMBER_EXPIRE_MINUTES == 180

    def test_default_jwt_admin_expire(self):
        s = self._make_settings()
        assert s.JWT_ADMIN_EXPIRE_MINUTES == 300

    def test_default_jwt_super_admin_expire(self):
        s = self._make_settings()
        assert s.JWT_SUPER_ADMIN_EXPIRE_MINUTES == 480

    def test_default_cookie_secure_false(self):
        s = self._make_settings()
        assert s.COOKIE_SECURE is False

    def test_default_cookie_samesite(self):
        s = self._make_settings()
        assert s.COOKIE_SAMESITE == "lax"

    def test_default_cookie_domain_empty(self):
        s = self._make_settings()
        assert s.COOKIE_DOMAIN == ""

    def test_default_cors_allow_credentials(self):
        s = self._make_settings()
        assert s.CORS_ALLOW_CREDENTIALS is True

    def test_default_minio_public_url_empty(self):
        s = self._make_settings()
        assert s.MINIO_PUBLIC_URL == ""

    def test_default_minio_use_ssl_false(self):
        s = self._make_settings()
        assert s.MINIO_USE_SSL is False

    def test_default_sentry_dsn_empty(self):
        s = self._make_settings()
        assert s.SENTRY_DSN == ""

    def test_default_sentry_traces_rate(self):
        s = self._make_settings()
        assert s.SENTRY_TRACES_SAMPLE_RATE == 0.1

    def test_default_dd_trace_disabled(self):
        s = self._make_settings()
        assert s.DD_TRACE_ENABLED is False

    def test_default_max_user_storage_bytes(self):
        s = self._make_settings()
        assert s.MAX_USER_STORAGE_BYTES == 1_073_741_824  # 1 GB

    def test_default_vt_api_key_empty(self):
        s = self._make_settings()
        assert s.VT_API_KEY == ""

    def test_default_log_level(self):
        s = self._make_settings()
        assert s.LOG_LEVEL == "DEBUG"

    def test_default_log_format(self):
        s = self._make_settings()
        assert s.LOG_FORMAT == "json"

    # -- Computed properties --

    def test_database_url_format(self):
        s = self._make_settings(
            POSTGRES_USER="user1",
            POSTGRES_PASSWORD="pass1",
            POSTGRES_HOST="dbhost",
            POSTGRES_PORT=5433,
            POSTGRES_DB="mydb",
        )
        assert s.DATABASE_URL == "postgresql+asyncpg://user1:pass1@dbhost:5433/mydb"

    def test_redis_url_format(self):
        s = self._make_settings(
            REDIS_PASSWORD="secret",
            REDIS_HOST="rhost",
            REDIS_PORT=6380,
        )
        assert s.REDIS_URL == "redis://:secret@rhost:6380/0"

    def test_cors_origins_list_single(self):
        s = self._make_settings(CORS_ORIGINS="http://localhost:3000")
        assert s.CORS_ORIGINS_LIST == ["http://localhost:3000"]

    def test_cors_origins_list_multiple(self):
        s = self._make_settings(CORS_ORIGINS="http://a.com, http://b.com")
        assert s.CORS_ORIGINS_LIST == ["http://a.com", "http://b.com"]

    def test_cors_origins_list_empty(self):
        s = self._make_settings(CORS_ORIGINS="")
        assert s.CORS_ORIGINS_LIST == []

    def test_cors_origins_list_trims_whitespace(self):
        s = self._make_settings(CORS_ORIGINS="  http://x.com ,  http://y.com  ")
        assert s.CORS_ORIGINS_LIST == ["http://x.com", "http://y.com"]

    def test_is_development_true(self):
        s = self._make_settings(FASTAPI_ENV="development")
        assert s.is_development is True

    def test_is_development_false_production(self):
        s = self._make_settings(FASTAPI_ENV="production")
        assert s.is_development is False

    # -- Env var override --

    def test_env_var_override(self):
        s = self._make_settings(FASTAPI_PORT=9999, FASTAPI_DEBUG=True)
        assert s.FASTAPI_PORT == 9999
        assert s.FASTAPI_DEBUG is True

    def test_int_type_coercion(self):
        """Pydantic should coerce string env values to correct types."""
        s = self._make_settings(FASTAPI_PORT=3000)
        assert isinstance(s.FASTAPI_PORT, int)

    def test_bool_type_coercion(self):
        s = self._make_settings(FASTAPI_DEBUG=True)
        assert isinstance(s.FASTAPI_DEBUG, bool)


# ---------------------------------------------------------------------------
# rate_limit.py
# ---------------------------------------------------------------------------

class TestRateLimit:
    """Test rate limiting via Lua script (mocked Redis)."""

    @pytest.mark.asyncio
    async def test_within_limit_returns_true(self, mock_redis):
        """When Lua script returns 1, rate limit is not exceeded."""
        mock_redis.eval = AsyncMock(return_value=1)

        with patch("app.core.rate_limit.get_redis", return_value=mock_redis):
            from app.core.rate_limit import check_rate_limit

            result = await check_rate_limit("test:key", max_count=10, window_seconds=60)

        assert result is True

    @pytest.mark.asyncio
    async def test_exceeded_limit_returns_false(self, mock_redis):
        """When Lua script returns 0, rate limit is exceeded."""
        mock_redis.eval = AsyncMock(return_value=0)

        with patch("app.core.rate_limit.get_redis", return_value=mock_redis):
            from app.core.rate_limit import check_rate_limit

            result = await check_rate_limit("test:key", max_count=5, window_seconds=60)

        assert result is False

    @pytest.mark.asyncio
    async def test_eval_called_with_correct_args(self, mock_redis):
        """Verify eval is called with the Lua script, 1 key, and stringified args."""
        mock_redis.eval = AsyncMock(return_value=1)

        with patch("app.core.rate_limit.get_redis", return_value=mock_redis):
            from app.core.rate_limit import _LUA_RATE_LIMIT, check_rate_limit

            await check_rate_limit("rate:login:1.2.3.4", max_count=5, window_seconds=120)

        mock_redis.eval.assert_called_once_with(
            _LUA_RATE_LIMIT, 1, "rate:login:1.2.3.4", "5", "120"
        )

    @pytest.mark.asyncio
    async def test_first_request_allowed(self, mock_redis):
        """First request (Lua INCR returns 1) should be allowed."""
        mock_redis.eval = AsyncMock(return_value=1)

        with patch("app.core.rate_limit.get_redis", return_value=mock_redis):
            from app.core.rate_limit import check_rate_limit

            result = await check_rate_limit("rate:new", max_count=1, window_seconds=60)

        assert result is True

    @pytest.mark.asyncio
    async def test_exactly_at_limit(self, mock_redis):
        """Request at exactly the limit (count == max_count) should be allowed."""
        # Lua script returns 1 when current <= max_count
        mock_redis.eval = AsyncMock(return_value=1)

        with patch("app.core.rate_limit.get_redis", return_value=mock_redis):
            from app.core.rate_limit import check_rate_limit

            result = await check_rate_limit("rate:exact", max_count=10, window_seconds=60)

        assert result is True

    @pytest.mark.asyncio
    async def test_one_over_limit(self, mock_redis):
        """Request one past the limit should be rejected (Lua returns 0)."""
        mock_redis.eval = AsyncMock(return_value=0)

        with patch("app.core.rate_limit.get_redis", return_value=mock_redis):
            from app.core.rate_limit import check_rate_limit

            result = await check_rate_limit("rate:over", max_count=10, window_seconds=60)

        assert result is False

    @pytest.mark.asyncio
    async def test_different_keys_are_independent(self, mock_redis):
        """Different keys should be tracked independently."""
        call_count = 0

        async def eval_side_effect(script, num_keys, key, *args):
            nonlocal call_count
            call_count += 1
            # First key allowed, second key rejected
            return 1 if key == "rate:a" else 0

        mock_redis.eval = AsyncMock(side_effect=eval_side_effect)

        with patch("app.core.rate_limit.get_redis", return_value=mock_redis):
            from app.core.rate_limit import check_rate_limit

            result_a = await check_rate_limit("rate:a", max_count=5, window_seconds=60)
            result_b = await check_rate_limit("rate:b", max_count=5, window_seconds=60)

        assert result_a is True
        assert result_b is False
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_result_not_one_is_false(self, mock_redis):
        """Any return value other than 1 should be treated as False."""
        mock_redis.eval = AsyncMock(return_value=2)

        with patch("app.core.rate_limit.get_redis", return_value=mock_redis):
            from app.core.rate_limit import check_rate_limit

            result = await check_rate_limit("rate:weird", max_count=5, window_seconds=60)

        assert result is False

    def test_lua_script_contains_incr(self):
        """Lua script must use INCR for atomic counter."""
        from app.core.rate_limit import _LUA_RATE_LIMIT

        assert "INCR" in _LUA_RATE_LIMIT

    def test_lua_script_contains_expire(self):
        """Lua script must set EXPIRE on first request."""
        from app.core.rate_limit import _LUA_RATE_LIMIT

        assert "EXPIRE" in _LUA_RATE_LIMIT

    def test_lua_script_sets_expire_only_on_first(self):
        """Lua script should only set EXPIRE when current == 1."""
        from app.core.rate_limit import _LUA_RATE_LIMIT

        assert "current == 1" in _LUA_RATE_LIMIT


# ---------------------------------------------------------------------------
# database.py
# ---------------------------------------------------------------------------

class TestDatabase:
    """Test database pool initialization and lifecycle."""

    @pytest.mark.asyncio
    async def test_init_db_pool_creates_pool(self):
        """init_db_pool should call asyncpg.create_pool with correct params."""
        mock_pool = AsyncMock()

        with patch("app.core.database.asyncpg.create_pool", new_callable=AsyncMock, return_value=mock_pool):
            import app.core.database as db_mod
            from app.core.database import init_db_pool

            result = await init_db_pool("postgresql+asyncpg://user:pass@host:5432/db")

        assert result is mock_pool
        # Cleanup
        db_mod._pool = None

    @pytest.mark.asyncio
    async def test_init_db_pool_strips_asyncpg_prefix(self):
        """DSN should have 'postgresql+asyncpg://' replaced with 'postgresql://'."""
        mock_pool = AsyncMock()

        with patch("app.core.database.asyncpg.create_pool", new_callable=AsyncMock, return_value=mock_pool) as mock_create:
            import app.core.database as db_mod
            from app.core.database import init_db_pool

            await init_db_pool("postgresql+asyncpg://user:pass@host:5432/db")

        mock_create.assert_called_once_with(
            dsn="postgresql://user:pass@host:5432/db",
            min_size=10,
            max_size=30,
            command_timeout=60,
        )
        # Cleanup
        db_mod._pool = None

    @pytest.mark.asyncio
    async def test_init_db_pool_parameters(self):
        """Pool should be created with min_size=10, max_size=30, command_timeout=60."""
        with patch("app.core.database.asyncpg.create_pool", new_callable=AsyncMock) as mock_create:
            import app.core.database as db_mod
            from app.core.database import init_db_pool

            await init_db_pool("postgresql://user:pass@host/db")

        _, kwargs = mock_create.call_args
        assert kwargs["min_size"] == 10
        assert kwargs["max_size"] == 30
        assert kwargs["command_timeout"] == 60
        # Cleanup
        db_mod._pool = None

    @pytest.mark.asyncio
    async def test_close_db_pool_closes_and_clears(self):
        """close_db_pool should close the pool and set _pool to None."""
        import app.core.database as db_mod

        mock_pool = AsyncMock()
        db_mod._pool = mock_pool

        await db_mod.close_db_pool()

        mock_pool.close.assert_called_once()
        assert db_mod._pool is None

    @pytest.mark.asyncio
    async def test_close_db_pool_noop_when_none(self):
        """close_db_pool should do nothing when pool is already None."""
        import app.core.database as db_mod

        db_mod._pool = None

        # Should not raise
        await db_mod.close_db_pool()
        assert db_mod._pool is None

    def test_get_pool_returns_pool_when_initialized(self):
        """get_pool should return the pool when it is initialized."""
        import app.core.database as db_mod

        mock_pool = MagicMock()
        db_mod._pool = mock_pool

        result = db_mod.get_pool()
        assert result is mock_pool

        # Cleanup
        db_mod._pool = None

    def test_get_pool_raises_when_not_initialized(self):
        """get_pool should raise RuntimeError when pool is None."""
        import app.core.database as db_mod

        db_mod._pool = None

        with pytest.raises(RuntimeError, match="Database pool is not initialized"):
            db_mod.get_pool()

    @pytest.mark.asyncio
    async def test_init_sets_global_pool(self):
        """After init_db_pool, get_pool should return the created pool."""
        import app.core.database as db_mod

        mock_pool = AsyncMock()

        with patch("app.core.database.asyncpg.create_pool", new_callable=AsyncMock, return_value=mock_pool):
            await db_mod.init_db_pool("postgresql://u:p@h/d")

        assert db_mod.get_pool() is mock_pool

        # Cleanup
        db_mod._pool = None

    @pytest.mark.asyncio
    async def test_close_then_get_raises(self):
        """After closing the pool, get_pool should raise RuntimeError."""
        import app.core.database as db_mod

        mock_pool = AsyncMock()
        db_mod._pool = mock_pool

        await db_mod.close_db_pool()

        with pytest.raises(RuntimeError):
            db_mod.get_pool()
