"""Tests for app.services.auth — session management, authentication, guest login."""

from unittest.mock import AsyncMock, patch

from tests.conftest import make_user_dict


class TestAuthenticateUser:
    @patch("app.services.auth.async_verify_password", new_callable=AsyncMock, return_value=True)
    @patch("app.services.auth.get_user_by_username")
    async def test_authenticate_user_success(self, mock_get_user, mock_verify):
        from app.services.auth import authenticate_user

        user = make_user_dict(username="alice")
        mock_get_user.return_value = user

        result = await authenticate_user("alice", "Password1")
        assert result is not None
        assert result["username"] == "alice"
        mock_verify.assert_called_once_with("Password1", user["password_hash"])

    @patch("app.services.auth.async_verify_password", new_callable=AsyncMock, return_value=False)
    @patch("app.services.auth.get_user_by_username")
    async def test_authenticate_user_wrong_password(self, mock_get_user, mock_verify):
        from app.services.auth import authenticate_user

        mock_get_user.return_value = make_user_dict(username="alice")
        result = await authenticate_user("alice", "wrongpass")
        assert result is None

    @patch("app.services.auth.get_user_by_username")
    async def test_authenticate_user_not_found(self, mock_get_user):
        from app.services.auth import authenticate_user

        mock_get_user.return_value = None
        result = await authenticate_user("nonexistent", "Password1")
        assert result is None

    @patch("app.services.auth.get_user_by_username")
    async def test_authenticate_user_deleted(self, mock_get_user):
        from app.services.auth import authenticate_user

        mock_get_user.return_value = make_user_dict(is_deleted=True)
        result = await authenticate_user("alice", "Password1")
        assert result is None


class TestCreateSession:
    @patch("app.services.auth.get_redis")
    @patch("app.services.auth.create_access_token")
    async def test_create_session(self, mock_create_token, mock_get_redis):
        from app.services.auth import create_session

        mock_create_token.return_value = ("token123", "jti-abc", None)
        redis = AsyncMock()
        mock_get_redis.return_value = redis

        token, ttl = await create_session("user-id-1", "MEMBER")
        assert token == "token123"
        assert ttl > 0
        redis.set.assert_called_once()


class TestDestroySession:
    @patch("app.services.auth.get_redis")
    async def test_destroy_session(self, mock_get_redis):
        from app.services.auth import destroy_session

        redis = AsyncMock()
        mock_get_redis.return_value = redis

        await destroy_session("user-id-1", "MEMBER", "jti-abc")
        redis.delete.assert_called_once()
        redis.set.assert_called_once()  # blacklist

    @patch("app.services.auth.get_redis")
    async def test_destroy_session_guest_no_counter(self, mock_get_redis):
        from app.services.auth import destroy_session

        redis = AsyncMock()
        mock_get_redis.return_value = redis

        await destroy_session("guest-id", "GUEST", "jti-abc")
        redis.delete.assert_called_once()
        redis.decr.assert_not_called()


class TestValidateSession:
    @patch("app.services.auth.get_redis")
    async def test_validate_session_valid(self, mock_get_redis):
        from app.services.auth import validate_session

        redis = AsyncMock()
        redis.exists = AsyncMock(return_value=0)  # blacklist miss
        redis.get = AsyncMock(return_value="jti-abc")  # stored jti matches
        mock_get_redis.return_value = redis

        result = await validate_session("user-id-1", "MEMBER", "jti-abc")
        assert result is True

    @patch("app.services.auth.get_redis")
    async def test_validate_session_jti_mismatch(self, mock_get_redis):
        from app.services.auth import validate_session

        redis = AsyncMock()
        redis.exists = AsyncMock(return_value=0)  # blacklist miss
        redis.get = AsyncMock(return_value="jti-other")  # stored jti doesn't match
        mock_get_redis.return_value = redis

        result = await validate_session("user-id-1", "MEMBER", "jti-abc")
        assert result is False

    @patch("app.services.auth.get_redis")
    async def test_validate_session_blacklisted(self, mock_get_redis):
        from app.services.auth import validate_session

        redis = AsyncMock()
        redis.exists = AsyncMock(return_value=1)  # blacklist hit
        mock_get_redis.return_value = redis

        result = await validate_session("user-id-1", "MEMBER", "jti-abc")
        assert result is False


class TestGuestLogin:
    @patch("app.services.auth.create_session")
    @patch("app.services.auth.get_redis")
    async def test_guest_login_success(self, mock_get_redis, mock_create_session):
        from app.services.auth import guest_login

        redis = AsyncMock()
        redis.eval = AsyncMock(return_value=6)
        mock_get_redis.return_value = redis
        mock_create_session.return_value = ("token-guest", 2700)

        result = await guest_login("Guest User")
        assert result is not None
        token, ttl = result
        assert token == "token-guest"
        assert ttl == 2700
        # Lua eval was called atomically
        redis.eval.assert_called_once()

    @patch("app.services.auth.get_redis")
    async def test_guest_login_limit_reached(self, mock_get_redis):
        from app.services.auth import guest_login

        redis = AsyncMock()
        redis.eval = AsyncMock(return_value=-1)
        mock_get_redis.return_value = redis

        result = await guest_login("Guest User")
        assert result is None

    @patch("app.services.auth.create_session")
    @patch("app.services.auth.get_redis")
    async def test_guest_login_lua_script_receives_correct_args(
        self, mock_get_redis, mock_create_session
    ):
        """Verify redis.eval is called with the Lua script, 1, key, MAX_GUESTS."""
        from app.services.auth import (
            MAX_GUESTS,
            _GUEST_COUNTER_KEY,
            _GUEST_INCR_LUA,
            guest_login,
        )

        redis = AsyncMock()
        redis.eval = AsyncMock(return_value=5)
        mock_get_redis.return_value = redis
        mock_create_session.return_value = ("tok", 2700)

        await guest_login("Guest")

        redis.eval.assert_called_once_with(
            _GUEST_INCR_LUA, 1, _GUEST_COUNTER_KEY, MAX_GUESTS
        )

    @patch("app.services.auth.get_redis")
    async def test_guest_counter_sync(self, mock_get_redis):
        """sync_guest_counter counts session keys and sets the counter."""
        from app.services.auth import sync_guest_counter

        async def _scan_sessions(*args, **kwargs):
            for key in [f"session:GUEST:{i}" for i in range(7)]:
                yield key

        redis = AsyncMock()
        redis.scan_iter = _scan_sessions
        redis.set = AsyncMock()
        mock_get_redis.return_value = redis

        await sync_guest_counter()

        from app.services.auth import _GUEST_COUNTER_KEY

        redis.set.assert_called_once_with(_GUEST_COUNTER_KEY, 7)

    @patch("app.services.auth.get_redis")
    async def test_decrement_guest_counter(self, mock_get_redis):
        """decrement_guest_counter decrements and clamps to zero."""
        from app.services.auth import decrement_guest_counter

        redis = AsyncMock()
        redis.decr = AsyncMock(return_value=4)
        mock_get_redis.return_value = redis

        await decrement_guest_counter()
        redis.decr.assert_called_once()
        # Positive value — no clamping needed
        redis.set.assert_not_called()

    @patch("app.services.auth.get_redis")
    async def test_decrement_guest_counter_clamps_to_zero(self, mock_get_redis):
        """If counter goes negative after DECR, it is clamped to 0."""
        from app.services.auth import _GUEST_COUNTER_KEY, decrement_guest_counter

        redis = AsyncMock()
        redis.decr = AsyncMock(return_value=-1)
        redis.set = AsyncMock()
        mock_get_redis.return_value = redis

        await decrement_guest_counter()
        redis.set.assert_called_once_with(_GUEST_COUNTER_KEY, 0)

    @patch("app.services.auth.get_redis")
    async def test_decrement_guest_ip_counter(self, mock_get_redis):
        """decrement_guest_ip_counter decrements the per-IP key."""
        from app.services.auth import decrement_guest_ip_counter

        redis = AsyncMock()
        redis.decr = AsyncMock(return_value=2)
        mock_get_redis.return_value = redis

        await decrement_guest_ip_counter("192.168.1.1")
        redis.decr.assert_called_once_with("guest:ip:192.168.1.1")
        # Positive value — no clamping needed
        redis.set.assert_not_called()

    @patch("app.services.auth.get_redis")
    async def test_decrement_guest_ip_counter_clamps_to_zero(self, mock_get_redis):
        """If per-IP counter goes negative after DECR, it is clamped to 0."""
        from app.services.auth import decrement_guest_ip_counter

        redis = AsyncMock()
        redis.decr = AsyncMock(return_value=-1)
        redis.set = AsyncMock()
        mock_get_redis.return_value = redis

        await decrement_guest_ip_counter("10.0.0.1")
        redis.decr.assert_called_once_with("guest:ip:10.0.0.1")
        redis.set.assert_called_once_with("guest:ip:10.0.0.1", 0)

    @patch("app.services.auth.get_redis")
    async def test_decrement_guest_ip_counter_restores_ttl_when_clamped(self, mock_get_redis):
        """When clamping to zero, redis.expire must be called to restore the 1-hour TTL."""
        from app.services.auth import decrement_guest_ip_counter

        redis = AsyncMock()
        redis.decr = AsyncMock(return_value=-1)
        redis.set = AsyncMock()
        redis.expire = AsyncMock()
        mock_get_redis.return_value = redis

        await decrement_guest_ip_counter("192.0.2.1")
        redis.expire.assert_called_once_with("guest:ip:192.0.2.1", 3600)

    @patch("app.services.auth.create_session")
    @patch("app.services.auth.get_redis")
    async def test_guest_login_lua_prevents_race(self, mock_get_redis, mock_create_session):
        """Simulate TOCTOU race: two concurrent requests both try to take the last slot.

        With the Lua script, only one succeeds (gets 30), the other gets -1 and is rejected.
        """
        import asyncio

        from app.services.auth import guest_login

        eval_counter = {"value": 29}

        async def _atomic_eval(script, num_keys, key, max_guests):
            """Simulate Lua INCR+limit: atomically increment and return new value or -1."""
            eval_counter["value"] += 1
            if eval_counter["value"] > max_guests:
                eval_counter["value"] -= 1
                return -1
            return eval_counter["value"]

        redis = AsyncMock()
        redis.eval = AsyncMock(side_effect=_atomic_eval)
        mock_get_redis.return_value = redis
        mock_create_session.return_value = ("tok", 2700)

        # Two concurrent guest_login calls — only one should succeed
        results = await asyncio.gather(
            guest_login("Guest A"),
            guest_login("Guest B"),
        )

        successes = [r for r in results if r is not None]
        failures = [r for r in results if r is None]

        assert len(successes) == 1, "Exactly one request should get the last slot"
        assert len(failures) == 1, "The other request should be rejected"
