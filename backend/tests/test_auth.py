"""Tests for app.services.auth — session management, authentication, guest login."""

from unittest.mock import AsyncMock, patch

from tests.conftest import make_user_dict


class TestAuthenticateUser:
    @patch("app.services.auth.verify_password", return_value=True)
    @patch("app.services.auth.get_user_by_username")
    async def test_authenticate_user_success(self, mock_get_user, mock_verify):
        from app.services.auth import authenticate_user

        user = make_user_dict(username="alice")
        mock_get_user.return_value = user

        result = await authenticate_user("alice", "Password1")
        assert result is not None
        assert result["username"] == "alice"
        mock_verify.assert_called_once_with("Password1", user["password_hash"])

    @patch("app.services.auth.verify_password", return_value=False)
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
    async def test_destroy_session_guest_decrements_counter(self, mock_get_redis):
        from app.services.auth import destroy_session

        redis = AsyncMock()
        mock_get_redis.return_value = redis

        await destroy_session("guest-id", "GUEST", "jti-abc")
        redis.decr.assert_called_once()


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
        redis.incr = AsyncMock(return_value=5)  # < 30
        mock_get_redis.return_value = redis
        mock_create_session.return_value = ("token-guest", 2700)

        result = await guest_login("Guest User")
        assert result is not None
        token, ttl = result
        assert token == "token-guest"
        assert ttl == 2700

    @patch("app.services.auth.get_redis")
    async def test_guest_login_limit_reached(self, mock_get_redis):
        from app.services.auth import guest_login

        redis = AsyncMock()
        redis.incr = AsyncMock(return_value=31)  # > MAX_GUESTS
        mock_get_redis.return_value = redis

        result = await guest_login("Guest User")
        assert result is None
        redis.decr.assert_called_once()
