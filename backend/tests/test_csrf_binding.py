"""Tests for CSRF token binding to session JTI (S18).

Covers:
- generate_csrf_token produces deterministic HMAC for a given JTI
- Different JTIs produce different CSRF tokens
- CSRF middleware rejects tokens not bound to the session JTI
- CSRF middleware accepts tokens correctly bound to the session JTI
- Middleware still accepts requests with no access_token cookie (graceful fallback)
"""

import uuid
from datetime import timedelta
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.csrf import generate_csrf_token


class TestGenerateCsrfToken:
    """Unit tests for generate_csrf_token()."""

    def test_deterministic_for_same_jti(self):
        """Same JTI always produces the same CSRF token."""
        jti = str(uuid.uuid4())
        token1 = generate_csrf_token(jti)
        token2 = generate_csrf_token(jti)
        assert token1 == token2

    def test_different_jtis_produce_different_tokens(self):
        """Different JTIs produce different CSRF tokens."""
        jti1 = str(uuid.uuid4())
        jti2 = str(uuid.uuid4())
        assert generate_csrf_token(jti1) != generate_csrf_token(jti2)

    def test_returns_hex_string(self):
        """CSRF token is a valid hex string (SHA-256 HMAC)."""
        token = generate_csrf_token("test-jti")
        assert len(token) == 64  # SHA-256 hex digest
        int(token, 16)  # Should not raise

    def test_bound_to_secret_key(self):
        """Token changes if SECRET_KEY changes."""
        jti = "test-jti"
        token1 = generate_csrf_token(jti)

        with patch("app.core.csrf.settings") as mock_settings:
            mock_settings.SECRET_KEY = "a_completely_different_secret_key_for_testing"
            token2 = generate_csrf_token(jti)

        assert token1 != token2


class TestCsrfBindingMiddleware:
    """Integration tests for CSRF middleware JTI binding."""

    @pytest.fixture
    async def _app_client(self):
        """Create a bare client (no pre-set cookies) for testing CSRF middleware."""
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

    def _make_jwt_and_csrf(self, user_id=None, role="MEMBER"):
        """Create a real JWT + matching CSRF token."""
        from app.core.security import create_access_token

        uid = user_id or str(uuid.uuid4())
        token, jti, _ = create_access_token(uid, role, timedelta(hours=1))
        csrf = generate_csrf_token(jti)
        return token, csrf, uid, jti

    @pytest.mark.anyio
    async def test_bound_csrf_accepted(self, _app_client: AsyncClient):
        """Request with CSRF token correctly bound to JWT JTI passes."""
        from app.core.deps import get_current_user
        from app.main import app

        jwt_token, csrf_token, uid, jti = self._make_jwt_and_csrf()

        app.dependency_overrides[get_current_user] = lambda: {
            "sub": uid,
            "role": "MEMBER",
            "jti": jti,
        }
        try:
            with patch(
                "app.api.v1.endpoints.auth.refresh_session_ttl",
                new_callable=AsyncMock,
                return_value=True,
            ), patch(
                "app.api.v1.endpoints.auth.check_rate_limit",
                new_callable=AsyncMock,
                return_value=True,
            ):
                resp = await _app_client.post(
                    "/api/v1/auth/heartbeat",
                    cookies={
                        "csrf_token": csrf_token,
                        "access_token": jwt_token,
                    },
                    headers={"X-CSRF-Token": csrf_token},
                )
            assert resp.status_code == 200
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.anyio
    async def test_unbound_csrf_rejected(self, _app_client: AsyncClient):
        """Request with CSRF token NOT bound to JWT JTI is rejected (403)."""
        from app.core.deps import get_current_user
        from app.main import app

        jwt_token, _correct_csrf, uid, jti = self._make_jwt_and_csrf()

        # Use a CSRF token bound to a different JTI
        wrong_csrf = generate_csrf_token("wrong-jti-value")

        app.dependency_overrides[get_current_user] = lambda: {
            "sub": uid,
            "role": "MEMBER",
            "jti": jti,
        }
        try:
            resp = await _app_client.post(
                "/api/v1/auth/heartbeat",
                cookies={
                    "csrf_token": wrong_csrf,
                    "access_token": jwt_token,
                },
                headers={"X-CSRF-Token": wrong_csrf},
            )
            assert resp.status_code == 403
            assert "not bound to session" in resp.json()["detail"]
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.anyio
    async def test_no_jwt_cookie_falls_back_to_double_submit(self, _app_client: AsyncClient):
        """Without access_token cookie, only double-submit check applies."""
        from app.core.deps import get_current_user
        from app.main import app

        plain_token = "plain-csrf-no-jwt-binding"

        app.dependency_overrides[get_current_user] = lambda: {
            "sub": str(uuid.uuid4()),
            "role": "MEMBER",
            "jti": "some-jti",
        }
        try:
            with patch(
                "app.api.v1.endpoints.auth.refresh_session_ttl",
                new_callable=AsyncMock,
                return_value=True,
            ), patch(
                "app.api.v1.endpoints.auth.check_rate_limit",
                new_callable=AsyncMock,
                return_value=True,
            ):
                resp = await _app_client.post(
                    "/api/v1/auth/heartbeat",
                    cookies={"csrf_token": plain_token},
                    headers={"X-CSRF-Token": plain_token},
                )
            # Without access_token cookie, JTI binding is skipped
            # Double-submit passes because cookie == header
            assert resp.status_code == 200
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.anyio
    async def test_login_sets_bound_csrf_token(self, _app_client: AsyncClient):
        """Login endpoint sets a CSRF token that is bound to the session JTI."""
        from app.core.security import decode_access_token
        from tests.conftest import make_user_dict

        user = make_user_dict(username="alice", role="MEMBER")

        with (
            patch(
                "app.api.v1.endpoints.auth.check_rate_limit",
                new_callable=AsyncMock,
                return_value=True,
            ),
            patch(
                "app.api.v1.endpoints.auth.verify_captcha",
                new_callable=AsyncMock,
                return_value=True,
            ),
            patch(
                "app.api.v1.endpoints.auth.authenticate_user",
                new_callable=AsyncMock,
                return_value=user,
            ),
            patch(
                "app.api.v1.endpoints.auth.has_consent",
                new_callable=AsyncMock,
                return_value=True,
            ),
            patch(
                "app.api.v1.endpoints.auth.create_session",
                new_callable=AsyncMock,
                return_value=("fake-jwt-token", "test-jti-123", 3600),
            ),
        ):
            resp = await _app_client.post(
                "/api/v1/auth/login",
                json={
                    "username": "alice",
                    "password": "Password1",
                    "captcha_id": "cap-1",
                    "captcha_code": "ABCD",
                },
            )

        assert resp.status_code == 200
        cookies = {c.name: c.value for c in resp.cookies.jar}
        assert "csrf_token" in cookies

        # The CSRF token should be the HMAC of the JTI
        expected_csrf = generate_csrf_token("test-jti-123")
        assert cookies["csrf_token"] == expected_csrf
