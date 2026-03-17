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
        default_prefs = {
            "theme": "light",
            "notify_mentions": True,
            "notify_replies": True,
            "notify_sig_posts": True,
        }

        try:
            _override_auth("MEMBER", user_id=user_id)
            with (
                patch(f"{_EP}.get_user_by_id", new_callable=AsyncMock, return_value=user),
                patch(
                    "app.services.preferences.get_user_preferences",
                    new_callable=AsyncMock,
                    return_value=default_prefs,
                ),
            ):
                resp = await client.get(
                    "/api/v1/users/me",
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 200
                assert resp.json()["username"] == "alice"
                assert resp.json()["preferences"] == default_prefs
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
        """DELETE /users/me → 200 when user is not sole admin of any SIG."""
        user_id = str(uuid.uuid4())

        try:
            payload, uid = _override_auth("MEMBER", user_id=user_id)
            with (
                patch(f"{_EP}.check_sole_admin_sigs", new_callable=AsyncMock, return_value=[]),
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

    @pytest.mark.anyio
    async def test_delete_account_blocked_sole_admin(self, client):
        """DELETE /users/me → 409 when user is the sole admin of a SIG."""
        user_id = str(uuid.uuid4())
        sig_id = uuid.uuid4()

        try:
            _override_auth("MEMBER", user_id=user_id)
            with patch(
                f"{_EP}.check_sole_admin_sigs",
                new_callable=AsyncMock,
                return_value=[{"id": sig_id, "name": "ML Research"}],
            ):
                resp = await client.delete(
                    "/api/v1/users/me",
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 409
                detail = resp.json()["detail"]["message"]
                assert "sole admin" in detail.lower()
                assert "ML Research" in detail
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_delete_account_blocked_multiple_sole_admin_sigs(self, client):
        """DELETE /users/me → 409 listing multiple SIG names."""
        user_id = str(uuid.uuid4())

        try:
            _override_auth("MEMBER", user_id=user_id)
            with patch(
                f"{_EP}.check_sole_admin_sigs",
                new_callable=AsyncMock,
                return_value=[
                    {"id": uuid.uuid4(), "name": "SIG Alpha"},
                    {"id": uuid.uuid4(), "name": "SIG Beta"},
                ],
            ):
                resp = await client.delete(
                    "/api/v1/users/me",
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 409
                detail = resp.json()["detail"]["message"]
                assert "SIG Alpha" in detail
                assert "SIG Beta" in detail
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
                        "password": "StrongPass1!",
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
                patch(f"{_EP}.emit", new_callable=AsyncMock),
                patch(
                    "app.services.auth.revoke_user_sessions",
                    new_callable=AsyncMock,
                ),
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
    async def test_bulk_change_role_revokes_sessions_and_emits(self, client):
        """PUT /users/bulk-role revokes sessions and emits event per user."""
        user_ids = [str(uuid.uuid4()), str(uuid.uuid4()), str(uuid.uuid4())]
        try:
            _override_auth("SUPER_ADMIN")
            with (
                patch(
                    "app.services.user.bulk_change_role",
                    new_callable=AsyncMock,
                    return_value=3,
                ),
                patch("app.services.audit.log_action", new_callable=AsyncMock),
                patch(
                    f"{_EP}.emit", new_callable=AsyncMock
                ) as mock_emit,
                patch(
                    "app.services.auth.revoke_user_sessions",
                    new_callable=AsyncMock,
                ) as mock_revoke,
            ):
                resp = await client.put(
                    "/api/v1/users/bulk-role",
                    json={"user_ids": user_ids, "role": "MEMBER"},
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 200
                assert resp.json()["updated_count"] == 3

                # emit called once per user with correct args
                assert mock_emit.call_count == len(user_ids)
                for uid in user_ids:
                    mock_emit.assert_any_call(
                        "user.role_changed", user_id=uid, new_role="MEMBER"
                    )

                # revoke_user_sessions called once per user
                assert mock_revoke.call_count == len(user_ids)
                for uid in user_ids:
                    mock_revoke.assert_any_call(uid)
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
            assert "Cannot change your own role" in resp.json()["detail"]["message"]
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
                    "password": "StrongPass1!",
                    "display_name": "New Admin",
                    "role": "ADMIN",
                },
                headers={"Authorization": "Bearer fake"},
            )
            assert resp.status_code == 403
            assert "Super Admin" in resp.json()["detail"]["message"]
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_admin_create_duplicate_username(self, client):
        """POST /users/admin/create-account with existing username → 409."""
        try:
            _override_auth("SUPER_ADMIN")
            with patch(f"{_EP}.user_exists_by_username", new_callable=AsyncMock, return_value=True):
                resp = await client.post(
                    "/api/v1/users/admin/create-account",
                    json={
                        "username": "existing",
                        "password": "StrongPass1!",
                        "display_name": "Dup User",
                        "role": "MEMBER",
                    },
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 409
                assert "already exists" in resp.json()["detail"]["message"].lower()
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


class TestChangeRoleEmitsEvent:
    @pytest.mark.anyio
    async def test_change_role_emits_user_role_changed(self, client):
        """PUT /users/{id}/role emits user.role_changed event."""
        target_user = uuid.uuid4()
        user = make_user_dict(user_id=str(target_user), role="ADMIN")

        try:
            _override_auth("SUPER_ADMIN")
            with (
                patch(
                    f"{_EP}.update_user_role",
                    new_callable=AsyncMock,
                    return_value=user,
                ),
                patch(
                    f"{_EP}.revoke_user_sessions",
                    new_callable=AsyncMock,
                ),
                patch(
                    f"{_EP}.emit",
                    new_callable=AsyncMock,
                ) as mock_emit,
            ):
                resp = await client.put(
                    f"/api/v1/users/{target_user}/role",
                    json={"role": "ADMIN"},
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 200

                # Verify user.role_changed was emitted
                calls = mock_emit.call_args_list
                role_changed_calls = [c for c in calls if c.args[0] == "user.role_changed"]
                assert len(role_changed_calls) == 1
                call_kwargs = role_changed_calls[0].kwargs
                assert call_kwargs["user_id"] == str(target_user)
                assert call_kwargs["new_role"] == "ADMIN"
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_change_role_emits_before_revoke(self, client):
        """user.role_changed is emitted before sessions are revoked."""
        target_user = uuid.uuid4()
        user = make_user_dict(user_id=str(target_user), role="MEMBER")
        call_order: list[str] = []

        async def track_emit(*args, **kwargs):
            call_order.append("emit")

        async def track_revoke(*args, **kwargs):
            call_order.append("revoke")

        try:
            _override_auth("SUPER_ADMIN")
            with (
                patch(
                    f"{_EP}.update_user_role",
                    new_callable=AsyncMock,
                    return_value=user,
                ),
                patch(
                    f"{_EP}.revoke_user_sessions",
                    side_effect=track_revoke,
                ),
                patch(
                    f"{_EP}.emit",
                    side_effect=track_emit,
                ),
            ):
                resp = await client.put(
                    f"/api/v1/users/{target_user}/role",
                    json={"role": "MEMBER"},
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 200
                # First emit is user.role_changed, then revoke
                assert call_order[0] == "emit"
                assert "revoke" in call_order
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


# ── N-B10: update_profile clear fields via null ────────────────────


class TestUpdateProfileClearFields:
    """N-B10: Verify endpoint passes only explicitly-set fields to the service."""

    @pytest.mark.anyio
    async def test_clear_bio_sends_null(self, client):
        """PUT /users/me with bio=null should pass bio=None to service."""
        user_id = str(uuid.uuid4())
        user = make_user_dict(user_id=user_id)
        user["bio"] = None

        try:
            _override_auth("MEMBER", user_id=user_id)
            with patch(
                f"{_EP}.update_user_profile", new_callable=AsyncMock, return_value=user
            ) as mock_update:
                resp = await client.put(
                    "/api/v1/users/me",
                    json={"bio": None},
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 200
                # bio=None must be passed to the service
                mock_update.assert_called_once()
                call_kwargs = mock_update.call_args[1]
                assert "bio" in call_kwargs
                assert call_kwargs["bio"] is None
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_omitted_fields_not_passed(self, client):
        """PUT /users/me with only display_name should NOT pass bio/orcid."""
        user_id = str(uuid.uuid4())
        user = make_user_dict(user_id=user_id)
        user["display_name"] = "New Name"

        try:
            _override_auth("MEMBER", user_id=user_id)
            with patch(
                f"{_EP}.update_user_profile", new_callable=AsyncMock, return_value=user
            ) as mock_update:
                resp = await client.put(
                    "/api/v1/users/me",
                    json={"display_name": "New Name"},
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 200
                call_kwargs = mock_update.call_args[1]
                # Only display_name should be passed, not bio/affiliation/orcid
                assert "display_name" in call_kwargs
                assert "bio" not in call_kwargs
                assert "affiliation" not in call_kwargs
                assert "orcid" not in call_kwargs
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_clear_all_optional_fields(self, client):
        """PUT /users/me clearing bio, affiliation, orcid simultaneously."""
        user_id = str(uuid.uuid4())
        user = make_user_dict(user_id=user_id)
        user["bio"] = None
        user["affiliation"] = None
        user["orcid"] = None

        try:
            _override_auth("MEMBER", user_id=user_id)
            with patch(
                f"{_EP}.update_user_profile", new_callable=AsyncMock, return_value=user
            ) as mock_update:
                resp = await client.put(
                    "/api/v1/users/me",
                    json={"bio": None, "affiliation": None, "orcid": None},
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 200
                call_kwargs = mock_update.call_args[1]
                assert call_kwargs["bio"] is None
                assert call_kwargs["affiliation"] is None
                assert call_kwargs["orcid"] is None
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_set_and_clear_mixed(self, client):
        """PUT /users/me setting display_name while clearing bio."""
        user_id = str(uuid.uuid4())
        user = make_user_dict(user_id=user_id)
        user["display_name"] = "Updated"
        user["bio"] = None

        try:
            _override_auth("MEMBER", user_id=user_id)
            with patch(
                f"{_EP}.update_user_profile", new_callable=AsyncMock, return_value=user
            ) as mock_update:
                resp = await client.put(
                    "/api/v1/users/me",
                    json={"display_name": "Updated", "bio": None},
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 200
                call_kwargs = mock_update.call_args[1]
                assert call_kwargs["display_name"] == "Updated"
                assert call_kwargs["bio"] is None
                # Omitted fields should not be in kwargs
                assert "affiliation" not in call_kwargs
        finally:
            _clear_overrides()
