"""
Tests for DM UX fixes:
  - P1: dm_friends_only exposed in public profile (GET /users/{id})
  - P2: user_repo.find_by_id LEFT JOINs user_preferences for dm_friends_only
  - Converters include dm_friends_only in PublicUserResponse
"""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest

from tests.conftest import make_user_dict

_EP_USERS = "app.api.v1.endpoints.users"


def make_public_user(user_id: str | None = None, dm_friends_only: bool = False) -> dict:
    """Return a fake user dict including dm_friends_only (as returned by updated find_by_id)."""
    u = make_user_dict(user_id=user_id)
    u["dm_friends_only"] = dm_friends_only
    return u


# ─── Helper: auth override ────────────────────────────────────────────────────


def _override_auth(role: str, app=None) -> None:
    """Inject a fake authenticated user into the FastAPI dependency overrides."""
    from app.core.deps import get_current_user
    from app.main import app as _app

    target = app or _app
    fake_id = str(uuid.uuid4())
    target.dependency_overrides[get_current_user] = lambda: {
        "sub": fake_id,
        "role": role,
    }


def _clear_overrides(app=None) -> None:
    from app.main import app as _app

    target = app or _app
    target.dependency_overrides.clear()


# ─── Part 1: PublicUserResponse schema includes dm_friends_only ──────────────


class TestPublicUserResponseSchema:
    def test_dm_friends_only_defaults_to_false(self):
        """PublicUserResponse.dm_friends_only defaults to False."""
        from app.schemas.user import PublicUserResponse

        resp = PublicUserResponse(
            id=str(uuid.uuid4()),
            username="alice",
            display_name="Alice",
            role="MEMBER",
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        assert resp.dm_friends_only is False

    def test_dm_friends_only_can_be_set_true(self):
        """PublicUserResponse.dm_friends_only can be set to True."""
        from app.schemas.user import PublicUserResponse

        resp = PublicUserResponse(
            id=str(uuid.uuid4()),
            username="bob",
            display_name="Bob",
            role="MEMBER",
            created_at=datetime.now(timezone.utc).isoformat(),
            dm_friends_only=True,
        )
        assert resp.dm_friends_only is True

    def test_dm_friends_only_serializes_in_json(self):
        """dm_friends_only appears in the serialized JSON output."""
        from app.schemas.user import PublicUserResponse

        resp = PublicUserResponse(
            id=str(uuid.uuid4()),
            username="carol",
            display_name="Carol",
            role="MEMBER",
            created_at=datetime.now(timezone.utc).isoformat(),
            dm_friends_only=True,
        )
        data = resp.model_dump()
        assert "dm_friends_only" in data
        assert data["dm_friends_only"] is True


# ─── Part 2: Converter includes dm_friends_only ───────────────────────────────


class TestUserConverterPublicResponse:
    @pytest.mark.anyio
    async def test_async_converter_includes_dm_friends_only_false(self):
        """async_user_to_public_response maps dm_friends_only=False from user dict."""
        from app.converters.user_converter import async_user_to_public_response

        user = make_public_user(dm_friends_only=False)
        with patch(
            "app.converters.user_converter.async_resolve_avatar_url",
            new_callable=AsyncMock,
            return_value=None,
        ):
            resp = await async_user_to_public_response(user)
        assert resp.dm_friends_only is False

    @pytest.mark.anyio
    async def test_async_converter_includes_dm_friends_only_true(self):
        """async_user_to_public_response maps dm_friends_only=True from user dict."""
        from app.converters.user_converter import async_user_to_public_response

        user = make_public_user(dm_friends_only=True)
        with patch(
            "app.converters.user_converter.async_resolve_avatar_url",
            new_callable=AsyncMock,
            return_value=None,
        ):
            resp = await async_user_to_public_response(user)
        assert resp.dm_friends_only is True

    def test_sync_converter_includes_dm_friends_only_false(self):
        """user_to_public_response maps dm_friends_only=False from user dict."""
        from app.converters.user_converter import user_to_public_response

        user = make_public_user(dm_friends_only=False)
        with patch("app.converters.user_converter.resolve_avatar_url", return_value=None):
            resp = user_to_public_response(user)
        assert resp.dm_friends_only is False

    def test_sync_converter_includes_dm_friends_only_true(self):
        """user_to_public_response maps dm_friends_only=True from user dict."""
        from app.converters.user_converter import user_to_public_response

        user = make_public_user(dm_friends_only=True)
        with patch("app.converters.user_converter.resolve_avatar_url", return_value=None):
            resp = user_to_public_response(user)
        assert resp.dm_friends_only is True

    def test_sync_converter_defaults_dm_friends_only_when_missing(self):
        """user_to_public_response defaults dm_friends_only to False when key absent."""
        from app.converters.user_converter import user_to_public_response

        user = make_user_dict()  # no dm_friends_only key
        with patch("app.converters.user_converter.resolve_avatar_url", return_value=None):
            resp = user_to_public_response(user)
        assert resp.dm_friends_only is False


# ─── Part 3: GET /users/{id} endpoint returns dm_friends_only ────────────────


class TestGetPublicProfileDmFriendsOnly:
    @pytest.mark.anyio
    async def test_endpoint_returns_dm_friends_only_false(self, client):
        """GET /users/{id} returns dm_friends_only: false when preference is off."""
        user_id = str(uuid.uuid4())
        user = make_public_user(user_id=user_id, dm_friends_only=False)

        try:
            _override_auth("MEMBER")
            with (
                patch(f"{_EP_USERS}.get_user_by_id", new_callable=AsyncMock, return_value=user),
                patch(
                    f"{_EP_USERS}.async_user_to_public_response",
                    new_callable=AsyncMock,
                ) as mock_converter,
            ):
                from app.schemas.user import PublicUserResponse

                mock_converter.return_value = PublicUserResponse(
                    id=user_id,
                    username=user["username"],
                    display_name=user["display_name"],
                    role=user["role"],
                    created_at=user["created_at"].isoformat(),
                    dm_friends_only=False,
                )
                resp = await client.get(f"/api/v1/users/{user_id}")
            assert resp.status_code == 200
            data = resp.json()
            assert "dm_friends_only" in data
            assert data["dm_friends_only"] is False
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_endpoint_returns_dm_friends_only_true(self, client):
        """GET /users/{id} returns dm_friends_only: true when preference is on."""
        user_id = str(uuid.uuid4())
        user = make_public_user(user_id=user_id, dm_friends_only=True)

        try:
            _override_auth("MEMBER")
            with (
                patch(f"{_EP_USERS}.get_user_by_id", new_callable=AsyncMock, return_value=user),
                patch(
                    f"{_EP_USERS}.async_user_to_public_response",
                    new_callable=AsyncMock,
                ) as mock_converter,
            ):
                from app.schemas.user import PublicUserResponse

                mock_converter.return_value = PublicUserResponse(
                    id=user_id,
                    username=user["username"],
                    display_name=user["display_name"],
                    role=user["role"],
                    created_at=user["created_at"].isoformat(),
                    dm_friends_only=True,
                )
                resp = await client.get(f"/api/v1/users/{user_id}")
            assert resp.status_code == 200
            data = resp.json()
            assert data["dm_friends_only"] is True
        finally:
            _clear_overrides()
