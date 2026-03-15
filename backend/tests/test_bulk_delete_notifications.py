"""Tests for Bug #14: bulk delete notifications must require notification_ids."""

import uuid
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


class TestBulkDeleteRequiresIds:
    """Verify DELETE /notifications returns 400 when no notification_ids provided."""

    @pytest.mark.anyio
    async def test_empty_body_returns_400(self, client):
        """DELETE /notifications with no body → 400."""
        try:
            _override_auth("MEMBER")
            with patch(f"{_EP}.check_rate_limit", new_callable=AsyncMock, return_value=True):
                resp = await client.delete(
                    "/api/v1/notifications",
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 400
                data = resp.json()
                assert data["detail"]["code"] == "SYS_422"
                assert "notification_ids" in data["detail"]["message"]
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_empty_notification_ids_list_returns_400(self, client):
        """DELETE /notifications with empty notification_ids → 400."""
        try:
            _override_auth("MEMBER")
            with patch(f"{_EP}.check_rate_limit", new_callable=AsyncMock, return_value=True):
                resp = await client.request(
                    "DELETE",
                    "/api/v1/notifications",
                    json={"notification_ids": []},
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 400
                data = resp.json()
                assert data["detail"]["code"] == "SYS_422"
                assert "notification_ids" in data["detail"]["message"]
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_null_notification_ids_returns_400(self, client):
        """DELETE /notifications with notification_ids: null → 400."""
        try:
            _override_auth("MEMBER")
            with patch(f"{_EP}.check_rate_limit", new_callable=AsyncMock, return_value=True):
                resp = await client.request(
                    "DELETE",
                    "/api/v1/notifications",
                    json={"notification_ids": None},
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 400
                data = resp.json()
                assert data["detail"]["code"] == "SYS_422"
                assert "notification_ids" in data["detail"]["message"]
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_valid_ids_returns_204(self, client):
        """DELETE /notifications with valid notification_ids → 204."""
        notif_ids = [str(uuid.uuid4()), str(uuid.uuid4())]

        try:
            _override_auth("MEMBER")
            with (
                patch(f"{_EP}.check_rate_limit", new_callable=AsyncMock, return_value=True),
                patch(
                    "app.repositories.notification_repo.bulk_delete",
                    new_callable=AsyncMock,
                    return_value=2,
                ),
            ):
                resp = await client.request(
                    "DELETE",
                    "/api/v1/notifications",
                    json={"notification_ids": notif_ids},
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 204
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_rate_limited_returns_429(self, client):
        """DELETE /notifications → 429 when rate limited."""
        try:
            _override_auth("MEMBER")
            with patch(f"{_EP}.check_rate_limit", new_callable=AsyncMock, return_value=False):
                resp = await client.request(
                    "DELETE",
                    "/api/v1/notifications",
                    json={"notification_ids": [str(uuid.uuid4())]},
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 429
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_bulk_delete_does_not_call_repo_when_empty(self, client):
        """DELETE /notifications with no IDs should NOT call notification_repo.bulk_delete."""
        try:
            _override_auth("MEMBER")
            with (
                patch(f"{_EP}.check_rate_limit", new_callable=AsyncMock, return_value=True),
                patch(
                    "app.repositories.notification_repo.bulk_delete",
                    new_callable=AsyncMock,
                ) as mock_bulk_delete,
            ):
                resp = await client.delete(
                    "/api/v1/notifications",
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 400
                mock_bulk_delete.assert_not_called()
        finally:
            _clear_overrides()
