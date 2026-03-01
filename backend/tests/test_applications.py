"""Tests for applications endpoints.

apply success, non-guest rejected, list admin, review approve.
"""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest

_EP = "app.api.v1.endpoints.applications"


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


def _make_application(user_id=None):
    now = datetime.now(timezone.utc)
    return {
        "id": uuid.uuid4(),
        "user_id": uuid.UUID(user_id) if user_id else uuid.uuid4(),
        "username": "guest1",
        "display_name": "Guest User",
        "description": "I'd like to join",
        "status": "PENDING",
        "reviewed_by": None,
        "reviewed_at": None,
        "created_at": now,
    }


class TestApplyMembership:
    @pytest.mark.anyio
    async def test_apply_success(self, client):
        """POST /users/apply-member → 200 for GUEST."""
        user_id = str(uuid.uuid4())

        try:
            _override_auth("GUEST", user_id=user_id)
            with patch(f"{_EP}.create_application", new_callable=AsyncMock):
                resp = await client.post(
                    "/api/v1/users/apply-member",
                    json={"description": "I'd like to join"},
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 200
                assert "submitted" in resp.json()["message"].lower()
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_non_guest_rejected(self, client):
        """POST /users/apply-member → 400 for non-GUEST."""
        try:
            _override_auth("MEMBER")
            resp = await client.post(
                "/api/v1/users/apply-member",
                json={"description": "Want to join"},
                headers={"Authorization": "Bearer fake"},
            )
            assert resp.status_code == 400
        finally:
            _clear_overrides()


class TestListApplications:
    @pytest.mark.anyio
    async def test_list_applications_admin(self, client):
        """GET /admin/applications → 200 for admin."""
        app_row = _make_application()

        try:
            _override_auth("ADMIN")
            with patch(
                f"{_EP}.list_applications", new_callable=AsyncMock, return_value=([app_row], 1)
            ):
                resp = await client.get(
                    "/api/v1/admin/applications",
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 200
                data = resp.json()
                assert data["total"] == 1
        finally:
            _clear_overrides()


class TestReviewApplication:
    @pytest.mark.anyio
    async def test_review_approve(self, client):
        """PUT /admin/applications/{id}/review → 200."""
        app_id = uuid.uuid4()
        app_row = _make_application()
        app_row["status"] = "APPROVED"

        try:
            _override_auth("ADMIN")
            with patch(f"{_EP}.review_application", new_callable=AsyncMock, return_value=app_row):
                resp = await client.put(
                    f"/api/v1/admin/applications/{app_id}/review",
                    json={"action": "APPROVED"},
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 200
                assert "approved" in resp.json()["message"].lower()
        finally:
            _clear_overrides()
