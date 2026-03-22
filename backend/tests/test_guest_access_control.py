"""Tests for GUEST role access restrictions (M-04, M-05, M-06, M-07).

Verifies that GUEST users are rejected (403) on endpoints that now
require MEMBER+ roles via require_role().
"""

import uuid
from datetime import timedelta
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.csrf import generate_csrf_token
from app.core.security import create_access_token


def _make_guest_auth():
    """Create a real GUEST JWT + matching CSRF token."""
    uid = str(uuid.uuid4())
    token, jti, _ = create_access_token(uid, "GUEST", timedelta(hours=1))
    csrf = generate_csrf_token(jti)
    return token, csrf, uid, jti


def _make_member_auth():
    """Create a real MEMBER JWT + matching CSRF token."""
    uid = str(uuid.uuid4())
    token, jti, _ = create_access_token(uid, "MEMBER", timedelta(hours=1))
    csrf = generate_csrf_token(jti)
    return token, csrf, uid, jti


@pytest.fixture
async def app_client():
    """Bare client with no pre-set cookies for manual auth control."""
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


def _guest_cookies_and_headers():
    """Return (cookies, headers) for a GUEST user with valid CSRF binding."""
    jwt_token, csrf_token, uid, jti = _make_guest_auth()
    cookies = {"access_token": jwt_token, "csrf_token": csrf_token}
    headers = {"X-CSRF-Token": csrf_token}
    return cookies, headers, uid


def _member_cookies_and_headers():
    """Return (cookies, headers) for a MEMBER user with valid CSRF binding."""
    jwt_token, csrf_token, uid, jti = _member_auth()
    cookies = {"access_token": jwt_token, "csrf_token": csrf_token}
    headers = {"X-CSRF-Token": csrf_token}
    return cookies, headers, uid


def _member_auth():
    return _make_member_auth()


class TestGuestCannotUpdateProfile:
    """M-04: PUT /users/me should reject GUEST with 403."""

    @pytest.mark.anyio
    async def test_guest_put_users_me_rejected(self, app_client: AsyncClient):
        cookies, headers, uid = _guest_cookies_and_headers()

        with patch(
            "app.core.deps.validate_session",
            new_callable=AsyncMock,
            return_value=True,
        ):
            resp = await app_client.put(
                "/api/v1/users/me",
                json={"display_name": "Hacker"},
                cookies=cookies,
                headers=headers,
            )
        assert resp.status_code == 403

    @pytest.mark.anyio
    async def test_member_put_users_me_not_rejected_by_role(self, app_client: AsyncClient):
        """MEMBER should pass the role check (may fail later in business logic)."""
        jwt_token, csrf_token, uid, jti = _make_member_auth()
        cookies = {"access_token": jwt_token, "csrf_token": csrf_token}
        headers = {"X-CSRF-Token": csrf_token}

        with (
            patch(
                "app.core.deps.validate_session",
                new_callable=AsyncMock,
                return_value=True,
            ),
            patch(
                "app.core.deps.get_user_by_id",
                new_callable=AsyncMock,
                return_value={"id": uid, "role": "MEMBER", "is_deleted": False, "is_banned": False},
            ),
            patch(
                "app.api.v1.endpoints.users.update_user_profile",
                new_callable=AsyncMock,
                return_value=None,
            ),
        ):
            resp = await app_client.put(
                "/api/v1/users/me",
                json={"display_name": "Valid"},
                cookies=cookies,
                headers=headers,
            )
        # Should NOT be 403 (role check passes); may be 404 (user not found) from business logic
        assert resp.status_code != 403


class TestGuestCannotAccessCoAuthorInvitations:
    """M-05: Co-author invitation endpoints should reject GUEST with 403."""

    @pytest.mark.anyio
    async def test_guest_get_invitations_rejected(self, app_client: AsyncClient):
        cookies, headers, uid = _guest_cookies_and_headers()

        with patch(
            "app.core.deps.validate_session",
            new_callable=AsyncMock,
            return_value=True,
        ):
            resp = await app_client.get(
                "/api/v1/users/me/co-author-invitations",
                cookies=cookies,
                headers=headers,
            )
        assert resp.status_code == 403

    @pytest.mark.anyio
    async def test_guest_accept_invitation_rejected(self, app_client: AsyncClient):
        cookies, headers, uid = _guest_cookies_and_headers()
        fake_id = str(uuid.uuid4())

        with patch(
            "app.core.deps.validate_session",
            new_callable=AsyncMock,
            return_value=True,
        ):
            resp = await app_client.put(
                f"/api/v1/users/me/co-author-invitations/{fake_id}/accept",
                cookies=cookies,
                headers=headers,
            )
        assert resp.status_code == 403

    @pytest.mark.anyio
    async def test_guest_reject_invitation_rejected(self, app_client: AsyncClient):
        cookies, headers, uid = _guest_cookies_and_headers()
        fake_id = str(uuid.uuid4())

        with patch(
            "app.core.deps.validate_session",
            new_callable=AsyncMock,
            return_value=True,
        ):
            resp = await app_client.put(
                f"/api/v1/users/me/co-author-invitations/{fake_id}/reject",
                cookies=cookies,
                headers=headers,
            )
        assert resp.status_code == 403


class TestGuestCannotViewQAVotes:
    """M-06: GET /qa/{post_id}/votes should reject GUEST with 403."""

    @pytest.mark.anyio
    async def test_guest_qa_votes_rejected(self, app_client: AsyncClient):
        cookies, headers, uid = _guest_cookies_and_headers()
        fake_post_id = str(uuid.uuid4())

        with patch(
            "app.core.deps.validate_session",
            new_callable=AsyncMock,
            return_value=True,
        ):
            resp = await app_client.get(
                f"/api/v1/qa/{fake_post_id}/votes",
                cookies=cookies,
                headers=headers,
            )
        assert resp.status_code == 403


class TestGuestCannotListStandaloneForms:
    """M-07: GET /forms should reject GUEST with 403."""

    @pytest.mark.anyio
    async def test_guest_list_forms_rejected(self, app_client: AsyncClient):
        cookies, headers, uid = _guest_cookies_and_headers()

        with patch(
            "app.core.deps.validate_session",
            new_callable=AsyncMock,
            return_value=True,
        ):
            resp = await app_client.get(
                "/api/v1/forms",
                cookies=cookies,
                headers=headers,
            )
        assert resp.status_code == 403
