"""Tests for S22: Session override notification in create_session."""

import json
from datetime import timedelta
from unittest.mock import AsyncMock, patch

import pytest

from app.services.auth import BLACKLIST_KEY_TEMPLATE, SESSION_KEY_TEMPLATE, create_session


@pytest.fixture
def mock_redis_session():
    """Mock Redis with publish support for session override tests."""
    redis = AsyncMock()
    redis.set = AsyncMock(return_value=True)
    redis.get = AsyncMock(return_value=None)
    redis.publish = AsyncMock(return_value=1)
    return redis


@pytest.mark.asyncio
async def test_create_session_publishes_force_logout_on_override(
    mock_redis_session: AsyncMock,
) -> None:
    """When an existing session exists, create_session should publish FORCE_LOGOUT."""
    user_id = "user-123"
    role = "MEMBER"
    old_jti = "old-jti-value"

    # Simulate existing session
    mock_redis_session.get = AsyncMock(return_value=old_jti)

    with (
        patch("app.services.auth.get_redis", return_value=mock_redis_session),
        patch(
            "app.services.auth.create_access_token",
            return_value=("new-token", "new-jti", None),
        ),
    ):
        token, jti, ttl = await create_session(user_id, role)

    assert token == "new-token"
    assert jti == "new-jti"

    # Verify FORCE_LOGOUT was published to ws:user:{user_id}
    publish_calls = [call for call in mock_redis_session.publish.call_args_list]
    assert len(publish_calls) == 1
    channel, payload = publish_calls[0].args
    assert channel == f"ws:user:{user_id}"
    msg = json.loads(payload)
    assert msg["type"] == "FORCE_LOGOUT"
    assert msg["reason"] == "logged_in_from_another_device"

    # Verify old JTI was blacklisted
    blacklist_key = BLACKLIST_KEY_TEMPLATE.format(jti=old_jti)
    set_calls = mock_redis_session.set.call_args_list
    # First set call should be the blacklist, second is the session key
    blacklist_call = set_calls[0]
    assert blacklist_call.args[0] == blacklist_key
    assert blacklist_call.args[1] == "1"
    assert blacklist_call.kwargs.get("ex") == 28800


@pytest.mark.asyncio
async def test_create_session_no_publish_when_no_existing_session(
    mock_redis_session: AsyncMock,
) -> None:
    """When no existing session, create_session should NOT publish FORCE_LOGOUT."""
    user_id = "user-456"
    role = "MEMBER"

    # No existing session
    mock_redis_session.get = AsyncMock(return_value=None)

    with (
        patch("app.services.auth.get_redis", return_value=mock_redis_session),
        patch(
            "app.services.auth.create_access_token",
            return_value=("token", "jti", None),
        ),
    ):
        token, jti, ttl = await create_session(user_id, role)

    assert token == "token"
    assert jti == "jti"

    # publish should NOT have been called
    mock_redis_session.publish.assert_not_called()

    # Only one set call (the session key), no blacklist
    assert mock_redis_session.set.call_count == 1
    session_key = SESSION_KEY_TEMPLATE.format(role=role, user_id=user_id)
    mock_redis_session.set.assert_called_once_with(session_key, "jti", ex=ttl)


@pytest.mark.asyncio
async def test_create_session_handles_bytes_old_jti(mock_redis_session: AsyncMock) -> None:
    """When Redis returns old JTI as bytes, it should be decoded properly."""
    user_id = "user-789"
    role = "ADMIN"
    old_jti_bytes = b"old-jti-bytes"

    mock_redis_session.get = AsyncMock(return_value=old_jti_bytes)

    with (
        patch("app.services.auth.get_redis", return_value=mock_redis_session),
        patch(
            "app.services.auth.create_access_token",
            return_value=("token", "jti", None),
        ),
    ):
        await create_session(user_id, role)

    # Verify the blacklist key uses the decoded string
    blacklist_key = BLACKLIST_KEY_TEMPLATE.format(jti="old-jti-bytes")
    set_calls = mock_redis_session.set.call_args_list
    assert set_calls[0].args[0] == blacklist_key


@pytest.mark.asyncio
async def test_create_session_returns_correct_ttl(mock_redis_session: AsyncMock) -> None:
    """create_session returns the TTL from ROLE_TTL_MAP."""
    mock_redis_session.get = AsyncMock(return_value=None)

    with (
        patch("app.services.auth.get_redis", return_value=mock_redis_session),
        patch(
            "app.services.auth.create_access_token",
            return_value=("tok", "jt", None),
        ),
        patch(
            "app.services.auth.ROLE_TTL_MAP",
            {"MEMBER": timedelta(hours=6)},
        ),
    ):
        token, jti, ttl = await create_session("u1", "MEMBER")

    assert ttl == 6 * 3600


@pytest.mark.asyncio
async def test_create_session_guest_no_override_notification(mock_redis_session: AsyncMock) -> None:
    """Guest sessions with no prior session should not trigger FORCE_LOGOUT."""
    mock_redis_session.get = AsyncMock(return_value=None)

    with (
        patch("app.services.auth.get_redis", return_value=mock_redis_session),
        patch(
            "app.services.auth.create_access_token",
            return_value=("guest-tok", "guest-jti", None),
        ),
    ):
        token, jti, ttl = await create_session("guest-id", "GUEST")

    assert token == "guest-tok"
    mock_redis_session.publish.assert_not_called()


@pytest.mark.asyncio
async def test_force_logout_message_structure(mock_redis_session: AsyncMock) -> None:
    """Verify the exact structure of the FORCE_LOGOUT pub/sub message."""
    mock_redis_session.get = AsyncMock(return_value="existing-jti")

    with (
        patch("app.services.auth.get_redis", return_value=mock_redis_session),
        patch(
            "app.services.auth.create_access_token",
            return_value=("t", "j", None),
        ),
    ):
        await create_session("uid", "MEMBER")

    channel, payload = mock_redis_session.publish.call_args.args
    msg = json.loads(payload)

    # Must have exactly these keys
    assert set(msg.keys()) == {"type", "reason"}
    assert msg["type"] == "FORCE_LOGOUT"
    assert msg["reason"] == "logged_in_from_another_device"
