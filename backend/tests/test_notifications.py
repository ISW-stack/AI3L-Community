"""Tests for notifications endpoints — list, mark read, mark all read."""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest

_EP = "app.api.v1.endpoints.notifications"


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


def _make_notification(user_id=None):
    now = datetime.now(timezone.utc).isoformat()
    return {
        "id": str(uuid.uuid4()),
        "action_type": "MENTION",
        "entity_type": "comment",
        "entity_id": str(uuid.uuid4()),
        "message": "Someone mentioned you",
        "is_read": False,
        "created_at": now,
        "trigger_user": {
            "id": str(uuid.uuid4()),
            "display_name": "TestUser",
            "avatar_url": None,
        },
    }


class TestListNotifications:
    @pytest.mark.anyio
    async def test_list_notifications(self, client):
        """GET /notifications → 200 with notification list."""
        user_id = str(uuid.uuid4())
        notif = _make_notification(user_id=user_id)

        try:
            _override_auth("MEMBER", user_id=user_id)
            with patch(f"{_EP}.list_notifications", new_callable=AsyncMock, return_value=([notif], 1, 1)):
                resp = await client.get(
                    "/api/v1/notifications",
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 200
                data = resp.json()
                assert data["total"] == 1
                assert data["unread_count"] == 1
                assert len(data["notifications"]) == 1
        finally:
            _clear_overrides()


class TestMarkRead:
    @pytest.mark.anyio
    async def test_mark_read(self, client):
        """PUT /notifications/{id}/read → 200."""
        notif_id = uuid.uuid4()

        try:
            _override_auth("MEMBER")
            with patch(f"{_EP}.mark_as_read", new_callable=AsyncMock, return_value=True):
                resp = await client.put(
                    f"/api/v1/notifications/{notif_id}/read",
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 200
        finally:
            _clear_overrides()


class TestMarkAllRead:
    @pytest.mark.anyio
    async def test_mark_all_read(self, client):
        """PUT /notifications/read-all → 200."""
        try:
            _override_auth("MEMBER")
            with patch(f"{_EP}.mark_all_as_read", new_callable=AsyncMock, return_value=5):
                resp = await client.put(
                    "/api/v1/notifications/read-all",
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 200
                assert "5" in resp.json()["message"]
        finally:
            _clear_overrides()
