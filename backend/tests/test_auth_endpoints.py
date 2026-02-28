"""Tests for app.api.v1.endpoints.auth — login, register, logout, guest, heartbeat."""

import uuid
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from tests.conftest import make_user_dict

# Patch targets: functions are imported into auth endpoint module at the top level
_EP = "app.api.v1.endpoints.auth"


class TestLoginEndpoint:
    @patch("app.services.privacy_consent.has_consent", new_callable=AsyncMock, return_value=True)
    @patch(f"{_EP}.create_session", new_callable=AsyncMock, return_value=("tok", 3600))
    @patch(f"{_EP}.authenticate_user", new_callable=AsyncMock)
    @patch(f"{_EP}.verify_captcha", new_callable=AsyncMock, return_value=True)
    async def test_login_success(
        self, mock_captcha, mock_auth, mock_session, mock_consent, client: AsyncClient
    ):
        user = make_user_dict(username="alice", role="MEMBER")
        mock_auth.return_value = user

        resp = await client.post("/api/v1/auth/login", json={
            "username": "alice",
            "password": "Password1",
            "captcha_id": "cap-1",
            "captcha_code": "ABCD",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["token"] == "tok"
        assert data["role"] == "MEMBER"

    @patch(f"{_EP}.verify_captcha", new_callable=AsyncMock, return_value=False)
    async def test_login_invalid_captcha(self, mock_captcha, client: AsyncClient):
        resp = await client.post("/api/v1/auth/login", json={
            "username": "alice",
            "password": "Password1",
            "captcha_id": "cap-1",
            "captcha_code": "WRONG",
        })
        assert resp.status_code == 400

    @patch(f"{_EP}.authenticate_user", new_callable=AsyncMock, return_value=None)
    @patch(f"{_EP}.verify_captcha", new_callable=AsyncMock, return_value=True)
    async def test_login_wrong_credentials(self, mock_captcha, mock_auth, client: AsyncClient):
        resp = await client.post("/api/v1/auth/login", json={
            "username": "alice",
            "password": "wrong",
            "captcha_id": "cap-1",
            "captcha_code": "ABCD",
        })
        assert resp.status_code == 401
        data = resp.json()
        assert data["detail"]["code"] == "AUTH_001"

    @patch(f"{_EP}.authenticate_user", new_callable=AsyncMock)
    @patch(f"{_EP}.verify_captcha", new_callable=AsyncMock, return_value=True)
    async def test_login_banned_user(self, mock_captcha, mock_auth, client: AsyncClient):
        user = make_user_dict(username="banned", is_banned=True, ban_reason="spam")
        mock_auth.return_value = user

        resp = await client.post("/api/v1/auth/login", json={
            "username": "banned",
            "password": "Password1",
            "captcha_id": "cap-1",
            "captcha_code": "ABCD",
        })
        assert resp.status_code == 403
        data = resp.json()
        assert data["detail"]["code"] == "AUTH_004"


class TestGuestLoginEndpoint:
    @patch(f"{_EP}.guest_login", new_callable=AsyncMock, return_value=("gtok", 2700))
    @patch(f"{_EP}.verify_captcha", new_callable=AsyncMock, return_value=True)
    @patch(f"{_EP}.get_invite_code", new_callable=AsyncMock)
    async def test_guest_login_success(self, mock_invite, mock_captcha, mock_guest, client: AsyncClient):
        mock_invite.return_value = {"code": "INV-123", "id": uuid.uuid4()}

        resp = await client.post("/api/v1/auth/guest/INV-123", json={
            "display_name": "Visitor",
            "captcha_id": "cap-1",
            "captcha_code": "ABCD",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["token"] == "gtok"
        assert data["role"] == "GUEST"
        assert data["requires_consent"] is True

    @patch(f"{_EP}.guest_login", new_callable=AsyncMock, return_value=None)
    @patch(f"{_EP}.verify_captcha", new_callable=AsyncMock, return_value=True)
    @patch(f"{_EP}.get_invite_code", new_callable=AsyncMock)
    async def test_guest_login_capacity_reached(self, mock_invite, mock_captcha, mock_guest, client: AsyncClient):
        mock_invite.return_value = {"code": "INV-123", "id": uuid.uuid4()}

        resp = await client.post("/api/v1/auth/guest/INV-123", json={
            "display_name": "Visitor",
            "captcha_id": "cap-1",
            "captcha_code": "ABCD",
        })
        assert resp.status_code == 429
        assert resp.json()["detail"]["code"] == "AUTH_003"


class TestRegisterEndpoint:
    @patch(f"{_EP}.create_session", new_callable=AsyncMock, return_value=("tok", 3600))
    @patch(f"{_EP}.create_user", new_callable=AsyncMock)
    @patch(f"{_EP}.user_exists_by_username", new_callable=AsyncMock, return_value=False)
    @patch(f"{_EP}.get_invite_code", new_callable=AsyncMock)
    @patch(f"{_EP}.verify_captcha", new_callable=AsyncMock, return_value=True)
    async def test_register_success(self, mock_captcha, mock_invite, mock_exists, mock_create, mock_session, client: AsyncClient):
        mock_invite.return_value = {"code": "VALID-CODE", "id": uuid.uuid4()}
        mock_create.return_value = make_user_dict(username="newuser", role="MEMBER")

        resp = await client.post("/api/v1/auth/register", json={
            "username": "newuser",
            "password": "Password1",
            "display_name": "New User",
            "invite_code": "VALID-CODE",
            "captcha_id": "cap-1",
            "captcha_code": "ABCD",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["token"] == "tok"
        assert data["requires_consent"] is True

    async def test_register_without_invite_code(self, client: AsyncClient):
        """POST /auth/register without invite_code → 422 validation error."""
        resp = await client.post("/api/v1/auth/register", json={
            "username": "newuser",
            "password": "Password1",
            "display_name": "New User",
            "captcha_id": "cap-1",
            "captcha_code": "ABCD",
        })
        assert resp.status_code == 422

    @patch(f"{_EP}.get_invite_code", new_callable=AsyncMock, return_value=None)
    @patch(f"{_EP}.verify_captcha", new_callable=AsyncMock, return_value=True)
    async def test_register_invalid_invite_code(self, mock_captcha, mock_invite, client: AsyncClient):
        """POST /auth/register with invalid invite code → 400."""
        resp = await client.post("/api/v1/auth/register", json={
            "username": "newuser",
            "password": "Password1",
            "display_name": "New User",
            "invite_code": "BAD-CODE",
            "captcha_id": "cap-1",
            "captcha_code": "ABCD",
        })
        assert resp.status_code == 400
        assert "invite code" in resp.json()["detail"].lower()

    @patch(f"{_EP}.get_invite_code", new_callable=AsyncMock)
    @patch(f"{_EP}.user_exists_by_username", new_callable=AsyncMock, return_value=True)
    @patch(f"{_EP}.verify_captcha", new_callable=AsyncMock, return_value=True)
    async def test_register_duplicate_username(self, mock_captcha, mock_exists, mock_invite, client: AsyncClient):
        mock_invite.return_value = {"code": "VALID-CODE", "id": uuid.uuid4()}
        resp = await client.post("/api/v1/auth/register", json={
            "username": "existing",
            "password": "Password1",
            "display_name": "Existing",
            "invite_code": "VALID-CODE",
            "captcha_id": "cap-1",
            "captcha_code": "ABCD",
        })
        assert resp.status_code == 409


class TestLogoutEndpoint:
    @patch(f"{_EP}.destroy_session", new_callable=AsyncMock)
    async def test_logout_success(self, mock_destroy, client: AsyncClient):
        from app.core.deps import get_current_user
        from app.main import app

        payload = {"sub": str(uuid.uuid4()), "role": "MEMBER", "jti": "jti-1"}
        app.dependency_overrides[get_current_user] = lambda: payload
        try:
            resp = await client.post("/api/v1/auth/logout", headers={"Authorization": "Bearer fake"})
            assert resp.status_code == 200
            mock_destroy.assert_called_once()
        finally:
            app.dependency_overrides.pop(get_current_user, None)


class TestHeartbeatEndpoint:
    @patch("app.services.auth.refresh_session_ttl", new_callable=AsyncMock, return_value=True)
    async def test_heartbeat_success(self, mock_refresh, client: AsyncClient):
        from app.core.deps import get_current_user
        from app.main import app

        payload = {"sub": str(uuid.uuid4()), "role": "MEMBER", "jti": "jti-1"}
        app.dependency_overrides[get_current_user] = lambda: payload
        try:
            resp = await client.post("/api/v1/auth/heartbeat", headers={"Authorization": "Bearer fake"})
            assert resp.status_code == 200
        finally:
            app.dependency_overrides.pop(get_current_user, None)
