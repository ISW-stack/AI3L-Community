"""Tests for atomic guest counter decrement (Bug #4).

Verifies that decrement_guest_counter() and decrement_guest_ip_counter()
use Lua scripts for atomic decrement-and-clamp instead of non-atomic
DECR + conditional SET.
"""

from unittest.mock import AsyncMock, patch

import pytest

from app.services.auth import (
    _GUEST_COUNTER_KEY,
    _GUEST_DECR_LUA,
    _GUEST_IP_DECR_LUA,
    decrement_guest_counter,
    decrement_guest_ip_counter,
)


class TestDecrementGuestCounterAtomic:
    """decrement_guest_counter uses a Lua script for atomicity."""

    @pytest.mark.asyncio
    async def test_calls_eval_with_lua_script(self, mock_redis):
        """Should use redis.eval with the decrement Lua script."""
        with patch("app.services.auth.get_redis", return_value=mock_redis):
            await decrement_guest_counter()

            mock_redis.eval.assert_awaited_once_with(
                _GUEST_DECR_LUA, 1, _GUEST_COUNTER_KEY
            )

    @pytest.mark.asyncio
    async def test_does_not_use_bare_decr(self, mock_redis):
        """Should NOT call redis.decr directly — that's the old non-atomic path."""
        with patch("app.services.auth.get_redis", return_value=mock_redis):
            await decrement_guest_counter()

            mock_redis.decr.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_does_not_call_set_directly(self, mock_redis):
        """Should NOT call redis.set directly — clamping is inside the Lua script."""
        with patch("app.services.auth.get_redis", return_value=mock_redis):
            await decrement_guest_counter()

            mock_redis.set.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_lua_script_contains_decr_and_clamp(self):
        """Verify the Lua script decrements and clamps to zero."""
        assert "DECR" in _GUEST_DECR_LUA
        assert "SET" in _GUEST_DECR_LUA
        assert "val < 0" in _GUEST_DECR_LUA
        assert "return 0" in _GUEST_DECR_LUA


class TestDecrementGuestIpCounterAtomic:
    """decrement_guest_ip_counter uses a Lua script for atomicity."""

    @pytest.mark.asyncio
    async def test_calls_eval_with_lua_script(self, mock_redis):
        """Should use redis.eval with the IP decrement Lua script."""
        with patch("app.services.auth.get_redis", return_value=mock_redis):
            await decrement_guest_ip_counter("192.168.1.1")

            mock_redis.eval.assert_awaited_once_with(
                _GUEST_IP_DECR_LUA, 1, "guest:ip:192.168.1.1", 3600
            )

    @pytest.mark.asyncio
    async def test_does_not_use_bare_decr(self, mock_redis):
        """Should NOT call redis.decr directly."""
        with patch("app.services.auth.get_redis", return_value=mock_redis):
            await decrement_guest_ip_counter("10.0.0.1")

            mock_redis.decr.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_does_not_call_set_or_expire_directly(self, mock_redis):
        """Clamping and TTL preservation are inside the Lua script."""
        with patch("app.services.auth.get_redis", return_value=mock_redis):
            await decrement_guest_ip_counter("10.0.0.1")

            mock_redis.set.assert_not_awaited()
            mock_redis.expire.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_ip_key_format(self, mock_redis):
        """The Redis key should follow the guest:ip:<ip> pattern."""
        with patch("app.services.auth.get_redis", return_value=mock_redis):
            await decrement_guest_ip_counter("203.0.113.42")

            call_args = mock_redis.eval.call_args
            assert call_args[0][2] == "guest:ip:203.0.113.42"

    @pytest.mark.asyncio
    async def test_default_ttl_is_3600(self, mock_redis):
        """The default TTL argument passed to the Lua script should be 3600."""
        with patch("app.services.auth.get_redis", return_value=mock_redis):
            await decrement_guest_ip_counter("10.0.0.1")

            call_args = mock_redis.eval.call_args
            assert call_args[0][3] == 3600

    @pytest.mark.asyncio
    async def test_lua_script_preserves_existing_ttl(self):
        """Verify the Lua script checks TTL before applying default EXPIRE."""
        assert "TTL" in _GUEST_IP_DECR_LUA
        assert "EXPIRE" in _GUEST_IP_DECR_LUA
        assert "ttl < 0" in _GUEST_IP_DECR_LUA
