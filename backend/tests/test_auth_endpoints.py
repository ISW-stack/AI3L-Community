"""Tests for app.api.v1.endpoints.auth.

login, register, logout, guest, heartbeat, ws-ticket, CSRF.
"""

import uuid
from unittest.mock import AsyncMock, patch

from httpx import AsyncClient

from tests.conftest import make_user_dict

# Patch targets: functions are imported into auth endpoint module at the top level
_EP = "app.api.v1.endpoints.auth"


class TestLoginEndpoint:
    @patch(f"{_EP}.check_rate_limit", new_callable=AsyncMock, return_value=True)
    @patch(f"{_EP}.has_consent", new_callable=AsyncMock, return_value=True)
    @patch(f"{_EP}.create_session", new_callable=AsyncMock, return_value=("tok", 3600))
    @patch(f"{_EP}.authenticate_user", new_callable=AsyncMock)
    @patch(f"{_EP}.verify_captcha", new_callable=AsyncMock, return_value=True)
    async def test_login_success(
        self, mock_captcha, mock_auth, mock_session, mock_consent, mock_rl, client: AsyncClient
    ):
        user = make_user_dict(username="alice", role="MEMBER")
        mock_auth.return_value = user

        resp = await client.post(
            "/api/v1/auth/login",
            json={
                "username": "alice",
                "password": "Password1",
                "captcha_id": "cap-1",
                "captcha_code": "ABCD",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        # Token is now in HttpOnly cookie, not in response body
        assert data["role"] == "MEMBER"
        assert "token" not in data
        # Check cookies are set
        cookies = {c.name: c for c in resp.cookies.jar}
        assert "access_token" in cookies
        assert "csrf_token" in cookies

    @patch(f"{_EP}.check_rate_limit", new_callable=AsyncMock, return_value=True)
    @patch(f"{_EP}.verify_captcha", new_callable=AsyncMock, return_value=False)
    async def test_login_invalid_captcha(self, mock_captcha, mock_rl, client: AsyncClient):
        resp = await client.post(
            "/api/v1/auth/login",
            json={
                "username": "alice",
                "password": "Password1",
                "captcha_id": "cap-1",
                "captcha_code": "WRONG",
            },
        )
        assert resp.status_code == 400

    @patch(f"{_EP}.check_rate_limit", new_callable=AsyncMock, return_value=True)
    @patch(f"{_EP}.authenticate_user", new_callable=AsyncMock, return_value=None)
    @patch(f"{_EP}.verify_captcha", new_callable=AsyncMock, return_value=True)
    async def test_login_wrong_credentials(
        self, mock_captcha, mock_auth, mock_rl, client: AsyncClient
    ):
        resp = await client.post(
            "/api/v1/auth/login",
            json={
                "username": "alice",
                "password": "wrong",
                "captcha_id": "cap-1",
                "captcha_code": "ABCD",
            },
        )
        assert resp.status_code == 401
        data = resp.json()
        assert data["detail"]["code"] == "AUTH_001"

    @patch(f"{_EP}.check_rate_limit", new_callable=AsyncMock, return_value=True)
    @patch(f"{_EP}.authenticate_user", new_callable=AsyncMock)
    @patch(f"{_EP}.verify_captcha", new_callable=AsyncMock, return_value=True)
    async def test_login_banned_user(self, mock_captcha, mock_auth, mock_rl, client: AsyncClient):
        user = make_user_dict(username="banned", is_banned=True, ban_reason="spam")
        mock_auth.return_value = user

        resp = await client.post(
            "/api/v1/auth/login",
            json={
                "username": "banned",
                "password": "Password1",
                "captcha_id": "cap-1",
                "captcha_code": "ABCD",
            },
        )
        assert resp.status_code == 403
        data = resp.json()
        assert data["detail"]["code"] == "AUTH_004"


class TestGuestLoginEndpoint:
    @patch(f"{_EP}.check_rate_limit", new_callable=AsyncMock, return_value=True)
    @patch(f"{_EP}.guest_login", new_callable=AsyncMock, return_value=("gtok", 2700))
    @patch(f"{_EP}.verify_captcha", new_callable=AsyncMock, return_value=True)
    @patch(f"{_EP}.get_invite_code", new_callable=AsyncMock)
    async def test_guest_login_success(
        self, mock_invite, mock_captcha, mock_guest, mock_rl, client: AsyncClient
    ):
        mock_invite.return_value = {"code": "INV-123", "id": uuid.uuid4()}

        resp = await client.post(
            "/api/v1/auth/guest/INV-123",
            json={
                "display_name": "Visitor",
                "captcha_id": "cap-1",
                "captcha_code": "ABCD",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["role"] == "GUEST"
        assert data["requires_consent"] is True
        # Token is now in cookie
        assert "token" not in data
        cookies = {c.name: c for c in resp.cookies.jar}
        assert "access_token" in cookies

    @patch(f"{_EP}.check_rate_limit", new_callable=AsyncMock, return_value=True)
    @patch(f"{_EP}.guest_login", new_callable=AsyncMock, return_value=None)
    @patch(f"{_EP}.verify_captcha", new_callable=AsyncMock, return_value=True)
    @patch(f"{_EP}.get_invite_code", new_callable=AsyncMock)
    async def test_guest_login_capacity_reached(
        self, mock_invite, mock_captcha, mock_guest, mock_rl, client: AsyncClient
    ):
        mock_invite.return_value = {"code": "INV-123", "id": uuid.uuid4()}

        resp = await client.post(
            "/api/v1/auth/guest/INV-123",
            json={
                "display_name": "Visitor",
                "captcha_id": "cap-1",
                "captcha_code": "ABCD",
            },
        )
        assert resp.status_code == 429
        assert resp.json()["detail"]["code"] == "AUTH_003"


class TestRegisterEndpoint:
    @patch(f"{_EP}.check_rate_limit", new_callable=AsyncMock, return_value=True)
    @patch(f"{_EP}.create_session", new_callable=AsyncMock, return_value=("tok", 3600))
    @patch(f"{_EP}.register_new_user", new_callable=AsyncMock)
    @patch(f"{_EP}.user_exists_by_username", new_callable=AsyncMock, return_value=False)
    @patch(f"{_EP}.get_invite_code", new_callable=AsyncMock)
    @patch(f"{_EP}.verify_captcha", new_callable=AsyncMock, return_value=True)
    async def test_register_success(
        self,
        mock_captcha,
        mock_invite,
        mock_exists,
        mock_register,
        mock_session,
        mock_rl,
        client: AsyncClient,
    ):
        mock_invite.return_value = {"code": "VALID-CODE", "id": uuid.uuid4()}
        mock_register.return_value = make_user_dict(username="newuser", role="MEMBER")

        resp = await client.post(
            "/api/v1/auth/register",
            json={
                "username": "newuser",
                "password": "Password1",
                "display_name": "New User",
                "invite_code": "VALID-CODE",
                "captcha_id": "cap-1",
                "captcha_code": "ABCD",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["requires_consent"] is True
        assert "token" not in data
        cookies = {c.name: c for c in resp.cookies.jar}
        assert "access_token" in cookies

    async def test_register_without_invite_code(self, client: AsyncClient):
        """POST /auth/register without invite_code → 422 validation error."""
        resp = await client.post(
            "/api/v1/auth/register",
            json={
                "username": "newuser",
                "password": "Password1",
                "display_name": "New User",
                "captcha_id": "cap-1",
                "captcha_code": "ABCD",
            },
        )
        assert resp.status_code == 422

    @patch(f"{_EP}.check_rate_limit", new_callable=AsyncMock, return_value=True)
    @patch(f"{_EP}.get_invite_code", new_callable=AsyncMock, return_value=None)
    @patch(f"{_EP}.verify_captcha", new_callable=AsyncMock, return_value=True)
    async def test_register_invalid_invite_code(
        self, mock_captcha, mock_invite, mock_rl, client: AsyncClient
    ):
        """POST /auth/register with invalid invite code → 400."""
        resp = await client.post(
            "/api/v1/auth/register",
            json={
                "username": "newuser",
                "password": "Password1",
                "display_name": "New User",
                "invite_code": "BAD-CODE",
                "captcha_id": "cap-1",
                "captcha_code": "ABCD",
            },
        )
        assert resp.status_code == 400
        assert "invite code" in resp.json()["detail"].lower()

    @patch(f"{_EP}.check_rate_limit", new_callable=AsyncMock, return_value=True)
    @patch(f"{_EP}.get_invite_code", new_callable=AsyncMock)
    @patch(f"{_EP}.user_exists_by_username", new_callable=AsyncMock, return_value=True)
    @patch(f"{_EP}.verify_captcha", new_callable=AsyncMock, return_value=True)
    async def test_register_duplicate_username(
        self, mock_captcha, mock_exists, mock_invite, mock_rl, client: AsyncClient
    ):
        mock_invite.return_value = {"code": "VALID-CODE", "id": uuid.uuid4()}
        resp = await client.post(
            "/api/v1/auth/register",
            json={
                "username": "existing",
                "password": "Password1",
                "display_name": "Existing",
                "invite_code": "VALID-CODE",
                "captcha_id": "cap-1",
                "captcha_code": "ABCD",
            },
        )
        assert resp.status_code == 409


class TestLogoutEndpoint:
    @patch(f"{_EP}.destroy_session", new_callable=AsyncMock)
    async def test_logout_success(self, mock_destroy, client: AsyncClient):
        from app.core.deps import get_current_user
        from app.main import app

        payload = {"sub": str(uuid.uuid4()), "role": "MEMBER", "jti": "jti-1"}
        app.dependency_overrides[get_current_user] = lambda: payload
        try:
            resp = await client.post(
                "/api/v1/auth/logout", headers={"Authorization": "Bearer fake"}
            )
            assert resp.status_code == 200
            mock_destroy.assert_called_once()
        finally:
            app.dependency_overrides.pop(get_current_user, None)


class TestHeartbeatEndpoint:
    @patch(f"{_EP}.refresh_session_ttl", new_callable=AsyncMock, return_value=True)
    async def test_heartbeat_success(self, mock_refresh, client: AsyncClient):
        from app.core.deps import get_current_user
        from app.main import app

        payload = {"sub": str(uuid.uuid4()), "role": "MEMBER", "jti": "jti-1"}
        app.dependency_overrides[get_current_user] = lambda: payload
        try:
            resp = await client.post(
                "/api/v1/auth/heartbeat", headers={"Authorization": "Bearer fake"}
            )
            assert resp.status_code == 200
        finally:
            app.dependency_overrides.pop(get_current_user, None)


class TestWsTicket:
    @patch(f"{_EP}.create_ws_ticket", new_callable=AsyncMock, return_value="test-ticket-abc")
    async def test_get_ws_ticket(self, mock_create_ticket, client: AsyncClient):
        """POST /auth/ws-ticket → 200 with ticket."""
        from app.core.deps import get_current_user
        from app.main import app

        payload = {"sub": str(uuid.uuid4()), "role": "MEMBER", "jti": "jti-1"}
        app.dependency_overrides[get_current_user] = lambda: payload
        try:
            resp = await client.post(
                "/api/v1/auth/ws-ticket", headers={"Authorization": "Bearer fake"}
            )
            assert resp.status_code == 200
            data = resp.json()
            assert "ticket" in data
            assert data["ticket"] == "test-ticket-abc"
        finally:
            app.dependency_overrides.pop(get_current_user, None)


class TestGetCaptcha:
    @patch(f"{_EP}.check_rate_limit", new_callable=AsyncMock, return_value=True)
    @patch(
        f"{_EP}.generate_captcha", new_callable=AsyncMock, return_value=("cap-id-1", "base64data")
    )
    async def test_get_captcha(self, mock_captcha, mock_rl, client: AsyncClient):
        """GET /auth/captcha → 200 with captcha_id and image."""
        resp = await client.get("/api/v1/auth/captcha")
        assert resp.status_code == 200
        data = resp.json()
        assert data["captcha_id"] == "cap-id-1"
        assert data["image_base64"] == "base64data"


class TestGenerateInviteCode:
    @patch(f"{_EP}.create_invite_code", new_callable=AsyncMock)
    async def test_generate_invite_code(self, mock_create, client: AsyncClient):
        """POST /auth/invite-code → 200 for member."""
        from datetime import datetime, timezone

        from app.core.deps import get_current_user
        from app.main import app

        mock_create.return_value = ("INV-NEWCODE", datetime(2026, 4, 1, tzinfo=timezone.utc))

        payload = {"sub": str(uuid.uuid4()), "role": "MEMBER", "jti": "jti-1"}
        app.dependency_overrides[get_current_user] = lambda: payload
        try:
            resp = await client.post(
                "/api/v1/auth/invite-code", headers={"Authorization": "Bearer fake"}
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["invite_code"] == "INV-NEWCODE"
        finally:
            app.dependency_overrides.pop(get_current_user, None)


class TestVerifyInviteCode:
    @patch(f"{_EP}.get_invite_code", new_callable=AsyncMock)
    async def test_verify_valid(self, mock_get, client: AsyncClient):
        """GET /auth/invite-code/{code} → 200 for valid code."""
        mock_get.return_value = {"code": "INV-VALID", "id": uuid.uuid4()}
        resp = await client.get("/api/v1/auth/invite-code/INV-VALID")
        assert resp.status_code == 200
        assert "valid" in resp.json()["message"].lower()

    @patch(f"{_EP}.get_invite_code", new_callable=AsyncMock, return_value=None)
    async def test_verify_invalid(self, mock_get, client: AsyncClient):
        """GET /auth/invite-code/{code} → 404 for invalid code."""
        resp = await client.get("/api/v1/auth/invite-code/BAD-CODE")
        assert resp.status_code == 404


class TestCSRFMiddleware:
    async def test_csrf_blocks_post_without_token(self, client: AsyncClient):
        """POST to a protected endpoint without CSRF token should be blocked."""
        from app.core.deps import get_current_user
        from app.main import app

        payload = {"sub": str(uuid.uuid4()), "role": "MEMBER", "jti": "jti-1"}
        app.dependency_overrides[get_current_user] = lambda: payload
        try:
            # Send request without CSRF header/cookie (override client defaults)
            resp = await client.post(
                "/api/v1/auth/heartbeat",
                headers={"Authorization": "Bearer fake", "X-CSRF-Token": ""},
                cookies={"csrf_token": ""},
            )
            assert resp.status_code == 403
            assert "CSRF" in resp.json()["detail"]
        finally:
            app.dependency_overrides.pop(get_current_user, None)

    async def test_csrf_allows_with_matching_token(self, client: AsyncClient):
        """POST with matching CSRF cookie + header should pass (default client has them)."""
        from app.core.deps import get_current_user
        from app.main import app

        payload = {"sub": str(uuid.uuid4()), "role": "MEMBER", "jti": "jti-1"}
        app.dependency_overrides[get_current_user] = lambda: payload

        with patch(f"{_EP}.refresh_session_ttl", new_callable=AsyncMock, return_value=True):
            try:
                resp = await client.post(
                    "/api/v1/auth/heartbeat",
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 200
            finally:
                app.dependency_overrides.pop(get_current_user, None)

    @patch(f"{_EP}.check_rate_limit", new_callable=AsyncMock, return_value=True)
    @patch(f"{_EP}.verify_captcha", new_callable=AsyncMock, return_value=False)
    async def test_csrf_exempt_login(self, mock_captcha, mock_rl, client: AsyncClient):
        """POST to login should be CSRF-exempt (works even without CSRF tokens)."""
        # The default client has CSRF tokens, but login is exempt so even
        # mismatched tokens shouldn't cause 403. Let's verify the endpoint works.
        resp = await client.post(
            "/api/v1/auth/login",
            json={
                "username": "x",
                "password": "x",
                "captcha_id": "x",
                "captcha_code": "x",
            },
        )
        # Should be 400 (bad captcha), not 403 (CSRF)
        assert resp.status_code == 400

    @patch(f"{_EP}.get_invite_code", new_callable=AsyncMock, return_value=None)
    async def test_csrf_allows_get(self, mock_get, client: AsyncClient):
        """GET requests should not require CSRF token."""
        resp = await client.get("/api/v1/auth/invite-code/TEST")
        # Should be 404 (not found), not 403 (CSRF)
        assert resp.status_code == 404
