"""Tests for admin dashboard and invite codes endpoints."""

import uuid
from unittest.mock import AsyncMock, patch

import pytest

_EP = "app.api.v1.endpoints.admin"


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


class TestDashboard:
    @pytest.mark.anyio
    async def test_dashboard_stats(self, client):
        """GET /admin/dashboard → 200 with stats."""
        stats = {
            "users": 42,
            "posts": 100,
            "sigs": 5,
            "forms": 10,
            "pending_reports": 3,
            "pending_applications": 2,
        }

        try:
            _override_auth("ADMIN")
            with patch(f"{_EP}.get_dashboard_stats", new_callable=AsyncMock, return_value=stats):
                resp = await client.get(
                    "/api/v1/admin/dashboard",
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 200
                data = resp.json()
                assert data["users"] == 42
                assert data["pending_reports"] == 3
        finally:
            _clear_overrides()


class TestInviteCodes:
    @pytest.mark.anyio
    async def test_list_invite_codes(self, client):
        """GET /admin/invite-codes → 200 with codes list."""
        codes = [
            {
                "id": str(uuid.uuid4()),
                "code": "INV-ABC123",
                "creator_id": str(uuid.uuid4()),
                "consumed_by": None,
                "consumed_at": None,
                "expires_at": None,
                "created_at": "2026-01-01T00:00:00+00:00",
                "creator_username": "admin",
                "consumed_by_username": None,
                "status": "active",
            }
        ]

        try:
            _override_auth("ADMIN")
            with patch(f"{_EP}.list_invite_codes", new_callable=AsyncMock, return_value=(codes, 1)):
                resp = await client.get(
                    "/api/v1/admin/invite-codes",
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 200
                data = resp.json()
                assert data["total"] == 1
                assert data["codes"][0]["status"] == "active"
        finally:
            _clear_overrides()
