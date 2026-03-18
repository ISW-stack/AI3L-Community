"""Tests for SUPER_ADMIN soft-delete user endpoint."""

import uuid
from unittest.mock import AsyncMock, patch

import pytest

from tests.conftest import make_user_dict

_EP = "app.api.v1.endpoints.users"


def _override_auth(role="SUPER_ADMIN", user_id=None):
    from app.core.deps import get_current_user
    from app.main import app

    uid = user_id or str(uuid.uuid4())
    payload = {"sub": uid, "role": role, "jti": str(uuid.uuid4())}
    app.dependency_overrides[get_current_user] = lambda: payload
    return payload, uid


def _clear_overrides():
    from app.main import app

    app.dependency_overrides.clear()


class TestAdminDeleteUser:
    @pytest.mark.anyio
    async def test_admin_delete_user_success(self, client):
        """DELETE /users/{user_id} -> 200 when target is a regular MEMBER."""
        admin_id = str(uuid.uuid4())
        target_id = uuid.uuid4()
        target_user = make_user_dict(user_id=str(target_id), role="MEMBER")

        try:
            _override_auth("SUPER_ADMIN", user_id=admin_id)
            with (
                patch(
                    f"{_EP}.get_user_by_id",
                    new_callable=AsyncMock,
                    return_value=target_user,
                ),
                patch(
                    f"{_EP}.check_sole_admin_sigs",
                    new_callable=AsyncMock,
                    return_value=[],
                ),
                patch(
                    f"{_EP}.anonymize_user",
                    new_callable=AsyncMock,
                    return_value=True,
                ),
                patch(f"{_EP}.revoke_user_sessions", new_callable=AsyncMock),
                patch(f"{_EP}.emit", new_callable=AsyncMock),
            ):
                resp = await client.delete(
                    f"/api/v1/users/{target_id}",
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 200
                assert "deleted" in resp.json()["message"].lower()
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_admin_delete_self_fails(self, client):
        """DELETE /users/{own_id} -> 400 when admin tries to delete themselves."""
        user_id = str(uuid.uuid4())

        try:
            _override_auth("SUPER_ADMIN", user_id=user_id)
            resp = await client.delete(
                f"/api/v1/users/{user_id}",
                headers={"Authorization": "Bearer fake"},
            )
            assert resp.status_code == 400
            assert "Cannot delete yourself" in resp.json()["detail"]["message"]
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_admin_delete_super_admin_fails(self, client):
        """DELETE /users/{user_id} -> 403 when target is a SUPER_ADMIN."""
        target_id = uuid.uuid4()
        target_user = make_user_dict(user_id=str(target_id), role="SUPER_ADMIN")

        try:
            _override_auth("SUPER_ADMIN")
            with patch(
                f"{_EP}.get_user_by_id",
                new_callable=AsyncMock,
                return_value=target_user,
            ):
                resp = await client.delete(
                    f"/api/v1/users/{target_id}",
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 403
                assert "Cannot delete a Super Admin" in resp.json()["detail"]["message"]
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_admin_delete_user_not_found(self, client):
        """DELETE /users/{user_id} -> 404 when target does not exist."""
        target_id = uuid.uuid4()

        try:
            _override_auth("SUPER_ADMIN")
            with patch(
                f"{_EP}.get_user_by_id",
                new_callable=AsyncMock,
                return_value=None,
            ):
                resp = await client.delete(
                    f"/api/v1/users/{target_id}",
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 404
                assert "not found" in resp.json()["detail"]["message"].lower()
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_admin_delete_user_sole_sig_admin(self, client):
        """DELETE /users/{user_id} -> 409 when target is sole admin of a SIG."""
        target_id = uuid.uuid4()
        target_user = make_user_dict(user_id=str(target_id), role="MEMBER")
        sig_id = uuid.uuid4()

        try:
            _override_auth("SUPER_ADMIN")
            with (
                patch(
                    f"{_EP}.get_user_by_id",
                    new_callable=AsyncMock,
                    return_value=target_user,
                ),
                patch(
                    f"{_EP}.check_sole_admin_sigs",
                    new_callable=AsyncMock,
                    return_value=[{"id": sig_id, "name": "NLP Research"}],
                ),
            ):
                resp = await client.delete(
                    f"/api/v1/users/{target_id}",
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 409
                detail = resp.json()["detail"]["message"]
                assert "sole admin" in detail.lower()
                assert "NLP Research" in detail
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_admin_delete_forbidden_for_member(self, client):
        """DELETE /users/{user_id} -> 403 for MEMBER role."""
        target_id = uuid.uuid4()

        try:
            _override_auth("MEMBER")
            resp = await client.delete(
                f"/api/v1/users/{target_id}",
                headers={"Authorization": "Bearer fake"},
            )
            assert resp.status_code == 403
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_admin_delete_forbidden_for_admin(self, client):
        """DELETE /users/{user_id} -> 403 for ADMIN role (not SUPER_ADMIN)."""
        target_id = uuid.uuid4()

        try:
            _override_auth("ADMIN")
            resp = await client.delete(
                f"/api/v1/users/{target_id}",
                headers={"Authorization": "Bearer fake"},
            )
            assert resp.status_code == 403
        finally:
            _clear_overrides()
