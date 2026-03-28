"""Tests for admin endpoints — dashboard, invite codes list, invite code delete."""

import uuid
from unittest.mock import AsyncMock, patch

import pytest

_EP = "app.api.v1.endpoints.admin"
_INVITE_REPO = "app.repositories.invite_code_repo"


def _override_auth(role="ADMIN", user_id=None):
    from app.core.deps import get_current_user
    from app.main import app

    uid = user_id or str(uuid.uuid4())
    payload = {"sub": uid, "role": role, "jti": str(uuid.uuid4())}
    app.dependency_overrides[get_current_user] = lambda: payload
    return payload, uid


def _clear_overrides():
    from app.main import app

    app.dependency_overrides.clear()


def _make_invite_code(code_id=None):
    return {
        "id": str(code_id or uuid.uuid4()),
        "code": "INVITE-" + str(uuid.uuid4())[:8].upper(),
        "created_by": str(uuid.uuid4()),
        "consumed_by": None,
        "consumed_at": None,
        "expires_at": None,
        "created_at": "2026-03-01T00:00:00+00:00",
        "creator_username": "adminuser",
        "consumed_by_username": None,
        "status": "active",
    }


class TestDashboard:
    @pytest.mark.anyio
    async def test_dashboard_returns_stats(self, client):
        """GET /admin/dashboard → 200 with stats dict."""
        stats = {
            "users": 42,
            "posts": 100,
            "sigs": 5,
            "forms": 3,
            "pending_reports": 2,
            "pending_applications": 1,
        }

        try:
            _override_auth("ADMIN")
            with (
                patch(f"{_EP}.get_dashboard_stats", new_callable=AsyncMock, return_value=stats),
                patch(f"{_EP}.check_rate_limit", new_callable=AsyncMock, return_value=True),
            ):
                resp = await client.get(
                    "/api/v1/admin/dashboard",
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 200
                data = resp.json()
                assert data["users"] == 42
                assert data["posts"] == 100
                assert data["pending_reports"] == 2
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_dashboard_super_admin_allowed(self, client):
        """GET /admin/dashboard → 200 for SUPER_ADMIN role."""
        stats = {
            "users": 10,
            "posts": 20,
            "sigs": 1,
            "forms": 0,
            "pending_reports": 0,
            "pending_applications": 0,
        }

        try:
            _override_auth("SUPER_ADMIN")
            with (
                patch(f"{_EP}.get_dashboard_stats", new_callable=AsyncMock, return_value=stats),
                patch(f"{_EP}.check_rate_limit", new_callable=AsyncMock, return_value=True),
            ):
                resp = await client.get(
                    "/api/v1/admin/dashboard",
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 200
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_dashboard_forbidden_for_member(self, client):
        """GET /admin/dashboard → 403 for MEMBER role."""
        try:
            _override_auth("MEMBER")
            with patch(f"{_EP}.get_dashboard_stats", new_callable=AsyncMock):
                resp = await client.get(
                    "/api/v1/admin/dashboard",
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 403
        finally:
            _clear_overrides()


class TestGetInviteCodes:
    @pytest.mark.anyio
    async def test_get_invite_codes_returns_list(self, client):
        """GET /admin/invite-codes → 200 with codes list."""
        code = _make_invite_code()

        try:
            _override_auth("ADMIN")
            with patch(
                f"{_EP}.list_invite_codes",
                new_callable=AsyncMock,
                return_value=([code], 1),
            ):
                resp = await client.get(
                    "/api/v1/admin/invite-codes",
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 200
                data = resp.json()
                assert data["total"] == 1
                assert len(data["codes"]) == 1
                assert data["codes"][0]["status"] == "active"
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_get_invite_codes_with_status_filter(self, client):
        """GET /admin/invite-codes?status=active → 200 passes filter to service."""
        code = _make_invite_code()

        try:
            _override_auth("ADMIN")
            with patch(
                f"{_EP}.list_invite_codes",
                new_callable=AsyncMock,
                return_value=([code], 1),
            ) as mock_list:
                resp = await client.get(
                    "/api/v1/admin/invite-codes?status=active",
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 200
                mock_list.assert_awaited_once()
                _, kwargs = mock_list.call_args
                assert kwargs.get("status_filter") == "active"
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_get_invite_codes_empty(self, client):
        """GET /admin/invite-codes → 200 with empty list when no codes exist."""
        try:
            _override_auth("ADMIN")
            with patch(
                f"{_EP}.list_invite_codes",
                new_callable=AsyncMock,
                return_value=([], 0),
            ):
                resp = await client.get(
                    "/api/v1/admin/invite-codes",
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 200
                data = resp.json()
                assert data["total"] == 0
                assert data["codes"] == []
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_get_invite_codes_forbidden_for_member(self, client):
        """GET /admin/invite-codes → 403 for MEMBER role."""
        try:
            _override_auth("MEMBER")
            with patch(f"{_EP}.list_invite_codes", new_callable=AsyncMock):
                resp = await client.get(
                    "/api/v1/admin/invite-codes",
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 403
        finally:
            _clear_overrides()


class TestDeleteInviteCode:
    @pytest.mark.anyio
    async def test_delete_invite_code_success(self, client):
        """DELETE /admin/invite-codes/{id} → 204 when code exists."""
        code_id = uuid.uuid4()

        try:
            _override_auth("ADMIN")
            with patch(
                f"{_INVITE_REPO}.delete",
                new_callable=AsyncMock,
                return_value=True,
            ):
                resp = await client.delete(
                    f"/api/v1/admin/invite-codes/{code_id}",
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 204
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_delete_invite_code_not_found(self, client):
        """DELETE /admin/invite-codes/{id} → 404 when code does not exist."""
        code_id = uuid.uuid4()

        try:
            _override_auth("ADMIN")
            with patch(
                f"{_INVITE_REPO}.delete",
                new_callable=AsyncMock,
                return_value=False,
            ):
                resp = await client.delete(
                    f"/api/v1/admin/invite-codes/{code_id}",
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 404
                assert "not found" in resp.json()["detail"]["message"].lower()
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_delete_invite_code_forbidden_for_member(self, client):
        """DELETE /admin/invite-codes/{id} → 403 for MEMBER role."""
        code_id = uuid.uuid4()

        try:
            _override_auth("MEMBER")
            with patch(f"{_INVITE_REPO}.delete", new_callable=AsyncMock):
                resp = await client.delete(
                    f"/api/v1/admin/invite-codes/{code_id}",
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 403
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_delete_invite_code_super_admin_allowed(self, client):
        """DELETE /admin/invite-codes/{id} → 204 for SUPER_ADMIN role."""
        code_id = uuid.uuid4()

        try:
            _override_auth("SUPER_ADMIN")
            with patch(
                f"{_INVITE_REPO}.delete",
                new_callable=AsyncMock,
                return_value=True,
            ):
                resp = await client.delete(
                    f"/api/v1/admin/invite-codes/{code_id}",
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 204
        finally:
            _clear_overrides()


class TestRevokeInviteCode:
    @pytest.mark.anyio
    async def test_revoke_invite_code_success(self, client):
        """PATCH /admin/invite-codes/{id}/revoke → 200 when code exists."""
        code_id = uuid.uuid4()

        try:
            _override_auth("ADMIN")
            with (
                patch(
                    f"{_INVITE_REPO}.revoke",
                    new_callable=AsyncMock,
                    return_value=True,
                ),
                patch("app.core.event_bus.emit", new_callable=AsyncMock),
            ):
                resp = await client.patch(
                    f"/api/v1/admin/invite-codes/{code_id}/revoke",
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 200
                assert "revoked" in resp.json()["message"].lower()
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_revoke_invite_code_not_found(self, client):
        """PATCH /admin/invite-codes/{id}/revoke → 404 when code not found."""
        code_id = uuid.uuid4()

        try:
            _override_auth("ADMIN")
            with patch(
                f"{_INVITE_REPO}.revoke",
                new_callable=AsyncMock,
                return_value=False,
            ):
                resp = await client.patch(
                    f"/api/v1/admin/invite-codes/{code_id}/revoke",
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 404
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_revoke_invite_code_forbidden_for_member(self, client):
        """PATCH /admin/invite-codes/{id}/revoke → 403 for MEMBER role."""
        code_id = uuid.uuid4()

        try:
            _override_auth("MEMBER")
            with patch(f"{_INVITE_REPO}.revoke", new_callable=AsyncMock):
                resp = await client.patch(
                    f"/api/v1/admin/invite-codes/{code_id}/revoke",
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 403
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_revoke_invite_code_super_admin_allowed(self, client):
        """PATCH /admin/invite-codes/{id}/revoke → 200 for SUPER_ADMIN role."""
        code_id = uuid.uuid4()

        try:
            _override_auth("SUPER_ADMIN")
            with (
                patch(
                    f"{_INVITE_REPO}.revoke",
                    new_callable=AsyncMock,
                    return_value=True,
                ),
                patch("app.core.event_bus.emit", new_callable=AsyncMock),
            ):
                resp = await client.patch(
                    f"/api/v1/admin/invite-codes/{code_id}/revoke",
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 200
        finally:
            _clear_overrides()
