"""Tests for about endpoints — contributors list and avatar proxy."""

import uuid
from unittest.mock import MagicMock, patch

import pytest

_EP = "app.api.v1.endpoints.about"


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


class TestListContributors:
    @pytest.mark.anyio
    async def test_list_contributors_member(self, client):
        """GET /about/contributors by MEMBER → 200 with contributor list."""
        try:
            _override_auth("MEMBER")
            resp = await client.get(
                "/api/v1/about/contributors",
                headers={"Authorization": "Bearer fake"},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert "contributors" in data
            assert len(data["contributors"]) >= 1
            # Should have avatar_url but NO github username
            for c in data["contributors"]:
                assert "avatar_url" in c
                assert "github" not in c
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_list_contributors_guest_forbidden(self, client):
        """GET /about/contributors by GUEST → 403."""
        try:
            _override_auth("GUEST")
            resp = await client.get(
                "/api/v1/about/contributors",
                headers={"Authorization": "Bearer fake"},
            )
            assert resp.status_code == 403
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_list_contributors_unauthenticated(self, client):
        """GET /about/contributors without auth → 401."""
        resp = await client.get("/api/v1/about/contributors")
        assert resp.status_code == 401


class TestContributorAvatar:
    @pytest.mark.anyio
    async def test_avatar_valid_id(self, client):
        """GET /about/contributors/0/avatar by MEMBER → 200 with image content."""
        from app.api.v1.endpoints import about as about_module

        # Clear avatar cache to ensure httpx is called
        about_module._avatar_cache.clear()

        try:
            _override_auth("MEMBER")
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.content = b"\x89PNG\r\n\x1a\n"
            mock_response.headers = {"content-type": "image/png"}

            with patch(f"{_EP}._requests.get", return_value=mock_response):
                resp = await client.get(
                    "/api/v1/about/contributors/0/avatar",
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 200
                assert resp.headers.get("content-type") == "image/png"
        finally:
            about_module._avatar_cache.clear()
            _clear_overrides()

    @pytest.mark.anyio
    async def test_avatar_invalid_id(self, client):
        """GET /about/contributors/999/avatar → 404."""
        try:
            _override_auth("MEMBER")
            resp = await client.get(
                "/api/v1/about/contributors/999/avatar",
                headers={"Authorization": "Bearer fake"},
            )
            assert resp.status_code == 404
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_avatar_guest_forbidden(self, client):
        """GET /about/contributors/0/avatar by GUEST → 403."""
        try:
            _override_auth("GUEST")
            resp = await client.get(
                "/api/v1/about/contributors/0/avatar",
                headers={"Authorization": "Bearer fake"},
            )
            assert resp.status_code == 403
        finally:
            _clear_overrides()
