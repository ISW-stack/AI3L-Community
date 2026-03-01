"""Tests for users endpoints — get profile, update profile, upload avatar invalid,
delete account, list users admin, list users forbidden, admin create, change role."""

import uuid
from unittest.mock import AsyncMock, patch

import pytest

from tests.conftest import make_user_dict

_EP = "app.api.v1.endpoints.users"


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


class TestGetProfile:
    @pytest.mark.anyio
    async def test_get_profile(self, client):
        """GET /users/me → 200."""
        user_id = str(uuid.uuid4())
        user = make_user_dict(user_id=user_id, username="alice")

        try:
            _override_auth("MEMBER", user_id=user_id)
            with patch(f"{_EP}.get_user_by_id", new_callable=AsyncMock, return_value=user):
                resp = await client.get(
                    "/api/v1/users/me",
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 200
                assert resp.json()["username"] == "alice"
        finally:
            _clear_overrides()


class TestUpdateProfile:
    @pytest.mark.anyio
    async def test_update_profile(self, client):
        """PUT /users/me → 200."""
        user_id = str(uuid.uuid4())
        user = make_user_dict(user_id=user_id)
        user["display_name"] = "New Name"

        try:
            _override_auth("MEMBER", user_id=user_id)
            with patch(f"{_EP}.update_user_profile", new_callable=AsyncMock, return_value=user):
                resp = await client.put(
                    "/api/v1/users/me",
                    json={"display_name": "New Name"},
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 200
                assert resp.json()["display_name"] == "New Name"
        finally:
            _clear_overrides()


class TestUploadAvatarInvalid:
    @pytest.mark.anyio
    async def test_upload_avatar_no_file(self, client):
        """PUT /users/me/avatar without file → 422."""
        try:
            _override_auth("MEMBER")
            resp = await client.put(
                "/api/v1/users/me/avatar",
                headers={"Authorization": "Bearer fake"},
            )
            assert resp.status_code == 422
        finally:
            _clear_overrides()


class TestDeleteAccount:
    @pytest.mark.anyio
    async def test_delete_account(self, client):
        """DELETE /users/me → 200."""
        user_id = str(uuid.uuid4())

        try:
            payload, uid = _override_auth("MEMBER", user_id=user_id)
            with (
                patch(f"{_EP}.anonymize_user", new_callable=AsyncMock, return_value=True),
                patch(f"{_EP}.destroy_session", new_callable=AsyncMock),
            ):
                resp = await client.delete(
                    "/api/v1/users/me",
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 200
        finally:
            _clear_overrides()


class TestListUsersAdmin:
    @pytest.mark.anyio
    async def test_list_users_admin(self, client):
        """GET /users → 200 for admin."""
        user = make_user_dict()

        try:
            _override_auth("ADMIN")
            with patch(f"{_EP}.list_users", new_callable=AsyncMock, return_value=([user], 1)):
                resp = await client.get(
                    "/api/v1/users",
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 200
                data = resp.json()
                assert data["total"] == 1
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_list_users_forbidden(self, client):
        """GET /users → 403 for regular member."""
        try:
            _override_auth("MEMBER")
            resp = await client.get(
                "/api/v1/users",
                headers={"Authorization": "Bearer fake"},
            )
            assert resp.status_code == 403
        finally:
            _clear_overrides()


class TestAdminCreateAccount:
    @pytest.mark.anyio
    async def test_admin_create_account(self, client):
        """POST /users/admin/create-account → 201."""
        user = make_user_dict(username="newadmin", role="ADMIN")

        try:
            _override_auth("SUPER_ADMIN")
            with (
                patch(f"{_EP}.user_exists_by_username", new_callable=AsyncMock, return_value=False),
                patch(f"{_EP}.create_user", new_callable=AsyncMock, return_value=user),
            ):
                resp = await client.post(
                    "/api/v1/users/admin/create-account",
                    json={
                        "username": "newadmin",
                        "password": "StrongPass1",
                        "display_name": "New Admin",
                        "role": "ADMIN",
                    },
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 201
        finally:
            _clear_overrides()


class TestChangeRole:
    @pytest.mark.anyio
    async def test_change_role(self, client, mock_redis):
        """PUT /users/{id}/role → 200 for super admin."""
        target_user = uuid.uuid4()
        user = make_user_dict(user_id=str(target_user), role="ADMIN")

        try:
            _override_auth("SUPER_ADMIN")
            with (
                patch(f"{_EP}.update_user_role", new_callable=AsyncMock, return_value=user),
                patch("app.core.redis.get_redis", return_value=mock_redis),
            ):
                resp = await client.put(
                    f"/api/v1/users/{target_user}/role",
                    json={"role": "ADMIN"},
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 200
        finally:
            _clear_overrides()
