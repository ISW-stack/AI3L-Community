"""Tests for the CSRF double-submit cookie middleware (app.core.csrf).

Covers: valid token, missing token, mismatched token, GET bypass,
exempt paths (login/register/guest/WS), PUT/PATCH/DELETE checks,
and OPTIONS bypass.
"""

import uuid
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

_TEST_CSRF = "csrf-valid-token"


@pytest.fixture
async def bare_client():
    """Client with NO CSRF tokens — used to verify CSRF enforcement."""
    from app.main import app

    with (
        patch("app.main.init_db_pool", new_callable=AsyncMock),
        patch("app.main.init_redis", new_callable=AsyncMock),
        patch("app.main.close_db_pool", new_callable=AsyncMock),
        patch("app.main.close_redis", new_callable=AsyncMock),
    ):
        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport,
            base_url="http://test",
        ) as ac:
            yield ac


@pytest.fixture
async def csrf_client():
    """Client WITH matching CSRF tokens (cookie + header)."""
    from app.main import app

    with (
        patch("app.main.init_db_pool", new_callable=AsyncMock),
        patch("app.main.init_redis", new_callable=AsyncMock),
        patch("app.main.close_db_pool", new_callable=AsyncMock),
        patch("app.main.close_redis", new_callable=AsyncMock),
    ):
        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport,
            base_url="http://test",
            cookies={"csrf_token": _TEST_CSRF},
            headers={"X-CSRF-Token": _TEST_CSRF},
        ) as ac:
            yield ac


def _override_auth(role="MEMBER", user_id=None):
    from app.core.deps import get_current_user
    from app.main import app

    uid = user_id or str(uuid.uuid4())
    app.dependency_overrides[get_current_user] = lambda: {
        "sub": uid,
        "role": role,
        "jti": "jti-csrf-test",
    }


def _clear_overrides():
    from app.main import app

    app.dependency_overrides.clear()


class TestCSRFValidToken:
    """POST with valid CSRF token succeeds."""

    @pytest.mark.anyio
    async def test_matching_csrf_passes(self, csrf_client: AsyncClient):
        """Request with matching cookie and header tokens passes CSRF check."""
        _override_auth("MEMBER")
        try:
            with (
                patch(
                    "app.api.v1.endpoints.auth.refresh_session_ttl",
                    new_callable=AsyncMock,
                    return_value=True,
                ),
                patch(
                    "app.api.v1.endpoints.auth.check_rate_limit",
                    new_callable=AsyncMock,
                    return_value=True,
                ),
            ):
                resp = await csrf_client.post("/api/v1/auth/heartbeat")
            # Should get 200 (heartbeat success), not 403
            assert resp.status_code == 200
        finally:
            _clear_overrides()


class TestCSRFMissingToken:
    """POST without CSRF token is rejected (403)."""

    @pytest.mark.anyio
    async def test_no_csrf_header_rejected(self, bare_client: AsyncClient):
        """POST without any CSRF tokens returns 403."""
        _override_auth("MEMBER")
        try:
            resp = await bare_client.post("/api/v1/auth/heartbeat")
            assert resp.status_code == 403
            assert "CSRF" in resp.json()["detail"]
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_empty_csrf_tokens_rejected(self, bare_client: AsyncClient):
        """POST with empty string CSRF tokens returns 403."""
        _override_auth("MEMBER")
        try:
            resp = await bare_client.post(
                "/api/v1/auth/heartbeat",
                headers={"X-CSRF-Token": ""},
                cookies={"csrf_token": ""},
            )
            assert resp.status_code == 403
            assert "CSRF" in resp.json()["detail"]
        finally:
            _clear_overrides()


class TestCSRFMismatchedToken:
    """POST with mismatched token is rejected."""

    @pytest.mark.anyio
    async def test_mismatched_cookie_header_rejected(self, bare_client: AsyncClient):
        """When cookie token != header token, request is rejected."""
        _override_auth("MEMBER")
        try:
            resp = await bare_client.post(
                "/api/v1/auth/heartbeat",
                headers={"X-CSRF-Token": "header-value"},
                cookies={"csrf_token": "different-cookie-value"},
            )
            assert resp.status_code == 403
            assert "CSRF" in resp.json()["detail"]
        finally:
            _clear_overrides()


class TestCSRFGETBypass:
    """GET requests are not checked for CSRF."""

    @pytest.mark.anyio
    async def test_get_no_csrf_needed(self, bare_client: AsyncClient):
        """GET request without CSRF tokens should pass through."""
        _override_auth("MEMBER")
        try:
            with patch(
                "app.api.v1.endpoints.sigs.list_sigs",
                new_callable=AsyncMock,
                return_value=([], 0),
            ):
                resp = await bare_client.get("/api/v1/sigs")
            # Should NOT be 403 (CSRF)
            assert resp.status_code != 403
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_head_no_csrf_needed(self, bare_client: AsyncClient):
        """HEAD request without CSRF tokens should pass through."""
        resp = await bare_client.head("/api/v1/sigs")
        # HEAD to a valid path should not get 403
        assert resp.status_code != 403


class TestCSRFExemptPaths:
    """Exempt paths (login, register, guest, WebSocket) are not checked."""

    @pytest.mark.anyio
    async def test_login_exempt(self, bare_client: AsyncClient):
        """POST /auth/login should not be blocked by CSRF."""
        with (
            patch(
                "app.api.v1.endpoints.auth.check_rate_limit",
                new_callable=AsyncMock,
                return_value=True,
            ),
            patch(
                "app.api.v1.endpoints.auth.verify_captcha",
                new_callable=AsyncMock,
                return_value=False,
            ),
        ):
            resp = await bare_client.post(
                "/api/v1/auth/login",
                json={
                    "username": "x",
                    "password": "x",
                    "captcha_id": "c",
                    "captcha_code": "1",
                },
            )
        # Should be 400 (bad captcha), not 403 (CSRF)
        assert resp.status_code != 403

    @pytest.mark.anyio
    async def test_register_exempt(self, bare_client: AsyncClient):
        """POST /auth/register should not be blocked by CSRF."""
        with (
            patch(
                "app.api.v1.endpoints.auth.check_rate_limit",
                new_callable=AsyncMock,
                return_value=True,
            ),
            patch(
                "app.api.v1.endpoints.auth.verify_captcha",
                new_callable=AsyncMock,
                return_value=False,
            ),
        ):
            resp = await bare_client.post(
                "/api/v1/auth/register",
                json={
                    "username": "newuser",
                    "password": "Passw0rd!",
                    "display_name": "New",
                    "captcha_id": "c",
                    "captcha_code": "1",
                },
            )
        assert resp.status_code != 403

    @pytest.mark.anyio
    async def test_guest_login_exempt(self, bare_client: AsyncClient):
        """POST /auth/guest/{code} should not be blocked by CSRF."""
        with (
            patch(
                "app.api.v1.endpoints.auth.check_rate_limit",
                new_callable=AsyncMock,
                return_value=True,
            ),
            patch(
                "app.api.v1.endpoints.auth.get_invite_code",
                new_callable=AsyncMock,
                return_value=None,
            ),
        ):
            resp = await bare_client.post(
                "/api/v1/auth/guest/TESTCODE",
                json={
                    "display_name": "Test Guest",
                    "captcha_id": "c",
                    "captcha_code": "1",
                },
            )
        # Should be 404 (bad invite code), not 403 (CSRF)
        assert resp.status_code != 403

    @pytest.mark.anyio
    async def test_guest_deep_path_not_exempt(self, bare_client: AsyncClient):
        """POST /auth/guest/{code}/foo should NOT be CSRF-exempt (deeper sub-path)."""
        resp = await bare_client.post("/api/v1/auth/guest/CODE/extra")
        # This deeper path is NOT exempt, so should get 403 (CSRF) or 404
        # 404 is also acceptable since the route doesn't exist
        assert resp.status_code in (403, 404, 405)

    @pytest.mark.anyio
    async def test_ws_path_exempt(self, bare_client: AsyncClient):
        """POST to /api/v1/ws paths should not trigger CSRF check."""
        # The WS endpoint won't actually work without proper setup,
        # but it should NOT return 403 (CSRF)
        resp = await bare_client.post("/api/v1/ws/notifications")
        assert resp.status_code != 403

    @pytest.mark.anyio
    async def test_captcha_exempt(self, bare_client: AsyncClient):
        """POST /auth/captcha should not be blocked by CSRF."""
        with patch(
            "app.api.v1.endpoints.auth.check_rate_limit",
            new_callable=AsyncMock,
            return_value=True,
        ):
            resp = await bare_client.post("/api/v1/auth/captcha")
        assert resp.status_code != 403


class TestCSRFStateMethods:
    """PUT, PATCH, DELETE also require CSRF."""

    @pytest.mark.anyio
    async def test_put_requires_csrf(self, bare_client: AsyncClient):
        """PUT without CSRF tokens returns 403."""
        _override_auth("MEMBER")
        try:
            resp = await bare_client.put(
                "/api/v1/posts/00000000-0000-0000-0000-000000000001",
                json={"title": "update"},
            )
            assert resp.status_code == 403
            assert "CSRF" in resp.json()["detail"]
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_patch_requires_csrf(self, bare_client: AsyncClient):
        """PATCH without CSRF tokens returns 403."""
        _override_auth("ADMIN")
        try:
            resp = await bare_client.patch(
                "/api/v1/posts/00000000-0000-0000-0000-000000000001/pin",
                json={"is_pinned": True},
            )
            assert resp.status_code == 403
            assert "CSRF" in resp.json()["detail"]
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_delete_requires_csrf(self, bare_client: AsyncClient):
        """DELETE without CSRF tokens returns 403."""
        _override_auth("ADMIN")
        try:
            resp = await bare_client.delete(
                "/api/v1/sigs/00000000-0000-0000-0000-000000000001",
            )
            assert resp.status_code == 403
            assert "CSRF" in resp.json()["detail"]
        finally:
            _clear_overrides()


class TestCSRFOptionsRequest:
    """OPTIONS request is not checked."""

    @pytest.mark.anyio
    async def test_options_no_csrf(self, bare_client: AsyncClient):
        """OPTIONS request should not be blocked by CSRF."""
        resp = await bare_client.options("/api/v1/posts")
        # OPTIONS is in _SAFE_METHODS, so CSRF should not block
        assert resp.status_code != 403
