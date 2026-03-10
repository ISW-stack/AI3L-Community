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
                patch(f"{_EP}.revoke_user_sessions", new_callable=AsyncMock),
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

    @pytest.mark.anyio
    async def test_list_users_with_search(self, client):
        """GET /users?search=alice → 200 with filtered results."""
        user = make_user_dict(username="alice")

        try:
            _override_auth("ADMIN")
            with patch(f"{_EP}.list_users", new_callable=AsyncMock, return_value=([user], 1)) as m:
                resp = await client.get(
                    "/api/v1/users?search=alice&page=1&page_size=20",
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 200
                data = resp.json()
                assert data["total"] == 1
                m.assert_called_once_with(page=1, page_size=20, search="alice")
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_list_users_with_page_params(self, client):
        """GET /users?page=2&page_size=10 → passes correct params."""
        try:
            _override_auth("ADMIN")
            with patch(f"{_EP}.list_users", new_callable=AsyncMock, return_value=([], 0)) as m:
                resp = await client.get(
                    "/api/v1/users?page=2&page_size=10",
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 200
                m.assert_called_once_with(page=2, page_size=10, search=None)
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_list_users_search_empty_result(self, client):
        """GET /users?search=nonexistent → 200 with empty list."""
        try:
            _override_auth("ADMIN")
            with patch(f"{_EP}.list_users", new_callable=AsyncMock, return_value=([], 0)):
                resp = await client.get(
                    "/api/v1/users?search=nonexistent",
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 200
                data = resp.json()
                assert data["total"] == 0
                assert data["users"] == []
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
    async def test_change_role(self, client):
        """PUT /users/{id}/role → 200 for super admin."""
        target_user = uuid.uuid4()
        user = make_user_dict(user_id=str(target_user), role="ADMIN")

        try:
            _override_auth("SUPER_ADMIN")
            with (
                patch(f"{_EP}.update_user_role", new_callable=AsyncMock, return_value=user),
                patch(f"{_EP}.revoke_user_sessions", new_callable=AsyncMock),
            ):
                resp = await client.put(
                    f"/api/v1/users/{target_user}/role",
                    json={"role": "ADMIN"},
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 200
        finally:
            _clear_overrides()


class TestBulkChangeRole:
    @pytest.mark.anyio
    async def test_bulk_change_role_super_admin(self, client):
        """PUT /users/bulk-role by SUPER_ADMIN → 200."""
        user_ids = [str(uuid.uuid4()), str(uuid.uuid4())]
        try:
            _override_auth("SUPER_ADMIN")
            with (
                patch(
                    "app.services.user.bulk_change_role",
                    new_callable=AsyncMock,
                    return_value=2,
                ),
                patch("app.services.audit.log_action", new_callable=AsyncMock),
            ):
                resp = await client.put(
                    "/api/v1/users/bulk-role",
                    json={"user_ids": user_ids, "role": "ADMIN"},
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 200
                assert resp.json()["updated_count"] == 2
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_bulk_change_role_forbidden_admin(self, client):
        """PUT /users/bulk-role by ADMIN (not SUPER_ADMIN) → 403."""
        try:
            _override_auth("ADMIN")
            resp = await client.put(
                "/api/v1/users/bulk-role",
                json={"user_ids": [str(uuid.uuid4())], "role": "MEMBER"},
                headers={"Authorization": "Bearer fake"},
            )
            assert resp.status_code == 403
        finally:
            _clear_overrides()


class TestChangeRoleSelfDemotion:
    @pytest.mark.anyio
    async def test_change_role_self_demotion(self, client):
        """PUT /users/{same_user_id}/role → 400 when changing own role."""
        user_id = str(uuid.uuid4())

        try:
            _override_auth("SUPER_ADMIN", user_id=user_id)
            resp = await client.put(
                f"/api/v1/users/{user_id}/role",
                json={"role": "MEMBER"},
                headers={"Authorization": "Bearer fake"},
            )
            assert resp.status_code == 400
            assert "Cannot change your own role" in resp.json()["detail"]
        finally:
            _clear_overrides()


class TestChangeRoleNotFound:
    @pytest.mark.anyio
    async def test_change_role_not_found(self, client):
        """PUT /users/{id}/role → 404 when user not found."""
        target_user = uuid.uuid4()

        try:
            _override_auth("SUPER_ADMIN")
            with patch(f"{_EP}.update_user_role", new_callable=AsyncMock, return_value=None):
                resp = await client.put(
                    f"/api/v1/users/{target_user}/role",
                    json={"role": "ADMIN"},
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 404
        finally:
            _clear_overrides()


class TestChangeRoleForbiddenAdmin:
    @pytest.mark.anyio
    async def test_change_role_forbidden_admin(self, client):
        """PUT /users/{id}/role → 403 for ADMIN (not SUPER_ADMIN)."""
        target_user = uuid.uuid4()

        try:
            _override_auth("ADMIN")
            resp = await client.put(
                f"/api/v1/users/{target_user}/role",
                json={"role": "MEMBER"},
                headers={"Authorization": "Bearer fake"},
            )
            assert resp.status_code == 403
        finally:
            _clear_overrides()


class TestAdminCreateAccountRestrictions:
    @pytest.mark.anyio
    async def test_admin_create_admin_by_admin_forbidden(self, client):
        """POST /users/admin/create-account with role=ADMIN by ADMIN → 403."""
        try:
            _override_auth("ADMIN")
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
            assert resp.status_code == 403
            assert "Super Admin" in resp.json()["detail"]
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_admin_create_duplicate_username(self, client):
        """POST /users/admin/create-account with existing username → 409."""
        try:
            _override_auth("SUPER_ADMIN")
            with patch(
                f"{_EP}.user_exists_by_username", new_callable=AsyncMock, return_value=True
            ):
                resp = await client.post(
                    "/api/v1/users/admin/create-account",
                    json={
                        "username": "existing",
                        "password": "StrongPass1",
                        "display_name": "Dup User",
                        "role": "MEMBER",
                    },
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 409
                assert "already exists" in resp.json()["detail"].lower()
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_admin_create_weak_password(self, client):
        """POST /users/admin/create-account with weak password → 400."""
        try:
            _override_auth("SUPER_ADMIN")
            resp = await client.post(
                "/api/v1/users/admin/create-account",
                json={
                    "username": "weakuser",
                    "password": "alllowercase1",
                    "display_name": "Weak User",
                    "role": "MEMBER",
                },
                headers={"Authorization": "Bearer fake"},
            )
            assert resp.status_code == 400
        finally:
            _clear_overrides()


class TestBanUserNotFound:
    @pytest.mark.anyio
    async def test_ban_user_not_found(self, client):
        """POST /users/{id}/ban → 404 when user not found."""
        target_user = uuid.uuid4()

        try:
            _override_auth("SUPER_ADMIN")
            with patch(f"{_EP}.ban_user", new_callable=AsyncMock, return_value=False):
                resp = await client.post(
                    f"/api/v1/users/{target_user}/ban",
                    json={"reason": "spam"},
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 404
        finally:
            _clear_overrides()
