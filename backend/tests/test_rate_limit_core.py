"""Tests for the rate limit core module (app.core.rate_limit).

Covers: first request allowed, exceeding limit denied, window reset,
independent keys, and Lua script return values.
"""

from unittest.mock import AsyncMock, patch

import pytest


class TestRateLimitFirstRequest:
    """First request within window is allowed."""

    @pytest.mark.anyio
    async def test_first_request_allowed(self, mock_redis):
        """check_rate_limit returns True for the first request (count=1)."""
        mock_redis.eval = AsyncMock(return_value=1)

        with patch("app.core.rate_limit.get_redis", return_value=mock_redis):
            from app.core.rate_limit import check_rate_limit

            result = await check_rate_limit("test:key:1", max_count=5, window_seconds=60)

        assert result is True
        mock_redis.eval.assert_called_once()

    @pytest.mark.anyio
    async def test_lua_script_passed_correctly(self, mock_redis):
        """The Lua script is called with correct arguments."""
        mock_redis.eval = AsyncMock(return_value=1)

        with patch("app.core.rate_limit.get_redis", return_value=mock_redis):
            from app.core.rate_limit import check_rate_limit

            await check_rate_limit("rl:login:user1", max_count=10, window_seconds=60)

        call_args = mock_redis.eval.call_args
        # Args: script, num_keys, key, max_count, window
        assert call_args[0][1] == 1  # num_keys
        assert call_args[0][2] == "rl:login:user1"  # key
        assert call_args[0][3] == "10"  # max_count as string
        assert call_args[0][4] == "60"  # window as string


class TestRateLimitExceeded:
    """Requests exceeding limit are denied."""

    @pytest.mark.anyio
    async def test_over_limit_returns_false(self, mock_redis):
        """check_rate_limit returns False when count > max_count (Lua returns 0)."""
        mock_redis.eval = AsyncMock(return_value=0)

        with patch("app.core.rate_limit.get_redis", return_value=mock_redis):
            from app.core.rate_limit import check_rate_limit

            result = await check_rate_limit("test:key:over", max_count=5, window_seconds=60)

        assert result is False

    @pytest.mark.anyio
    async def test_exactly_at_limit_is_allowed(self, mock_redis):
        """When count == max_count, Lua returns 1 (still within limit)."""
        mock_redis.eval = AsyncMock(return_value=1)

        with patch("app.core.rate_limit.get_redis", return_value=mock_redis):
            from app.core.rate_limit import check_rate_limit

            result = await check_rate_limit("test:key:exact", max_count=5, window_seconds=60)

        assert result is True


class TestRateLimitWindowReset:
    """Window expires and counter resets."""

    @pytest.mark.anyio
    async def test_after_window_reset_allowed(self, mock_redis):
        """After window expiry, the next request is allowed (Lua returns 1 again)."""
        # Simulate: first call returns 0 (exceeded), second returns 1 (reset)
        mock_redis.eval = AsyncMock(side_effect=[0, 1])

        with patch("app.core.rate_limit.get_redis", return_value=mock_redis):
            from app.core.rate_limit import check_rate_limit

            result1 = await check_rate_limit("test:key:reset", max_count=1, window_seconds=1)
            result2 = await check_rate_limit("test:key:reset", max_count=1, window_seconds=1)

        assert result1 is False
        assert result2 is True


class TestRateLimitIndependentKeys:
    """Different keys have independent limits."""

    @pytest.mark.anyio
    async def test_different_keys_independent(self, mock_redis):
        """Two different keys can each use their own limit independently."""
        call_count = {"user1": 0, "user2": 0}

        async def mock_eval(script, num_keys, key, *args):
            if "user1" in key:
                call_count["user1"] += 1
                return 1 if call_count["user1"] <= 2 else 0
            elif "user2" in key:
                call_count["user2"] += 1
                return 1
            return 1

        mock_redis.eval = mock_eval

        with patch("app.core.rate_limit.get_redis", return_value=mock_redis):
            from app.core.rate_limit import check_rate_limit

            r1_a = await check_rate_limit("rl:test:user1", max_count=2, window_seconds=60)
            r1_b = await check_rate_limit("rl:test:user1", max_count=2, window_seconds=60)
            r1_c = await check_rate_limit("rl:test:user1", max_count=2, window_seconds=60)
            r2_a = await check_rate_limit("rl:test:user2", max_count=2, window_seconds=60)

        assert r1_a is True
        assert r1_b is True
        assert r1_c is False  # user1 exceeded
        assert r2_a is True  # user2 still has quota


class TestRateLimitLuaScript:
    """The Lua script returns correct count."""

    @pytest.mark.anyio
    async def test_lua_returns_1_for_allowed(self, mock_redis):
        """Lua returns 1 (truthy) when within limit."""
        mock_redis.eval = AsyncMock(return_value=1)

        with patch("app.core.rate_limit.get_redis", return_value=mock_redis):
            from app.core.rate_limit import check_rate_limit

            result = await check_rate_limit("test:lua:1", max_count=10, window_seconds=60)

        assert result is True

    @pytest.mark.anyio
    async def test_lua_returns_0_for_denied(self, mock_redis):
        """Lua returns 0 (falsy) when over limit."""
        mock_redis.eval = AsyncMock(return_value=0)

        with patch("app.core.rate_limit.get_redis", return_value=mock_redis):
            from app.core.rate_limit import check_rate_limit

            result = await check_rate_limit("test:lua:0", max_count=10, window_seconds=60)

        assert result is False

    @pytest.mark.anyio
    async def test_non_1_truthy_treated_as_false(self, mock_redis):
        """Lua returns 2 (truthy but != 1) — should return False per `result == 1`."""
        mock_redis.eval = AsyncMock(return_value=2)

        with patch("app.core.rate_limit.get_redis", return_value=mock_redis):
            from app.core.rate_limit import check_rate_limit

            result = await check_rate_limit("test:lua:2", max_count=10, window_seconds=60)

        # The function does `bool(result == 1)` so 2 != 1 → False
        assert result is False

    @pytest.mark.anyio
    async def test_lua_script_content(self):
        """The Lua script text contains the expected INCR + EXPIRE logic."""
        from app.core.rate_limit import _LUA_RATE_LIMIT

        assert "INCR" in _LUA_RATE_LIMIT
        assert "EXPIRE" in _LUA_RATE_LIMIT
        assert "KEYS[1]" in _LUA_RATE_LIMIT
        assert "ARGV[1]" in _LUA_RATE_LIMIT
        assert "ARGV[2]" in _LUA_RATE_LIMIT
