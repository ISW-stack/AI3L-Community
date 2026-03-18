"""Tests for DELETE /notifications bulk delete (clear all + selective)."""

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


class TestBulkDeleteNotifications:
    """DELETE /notifications supports both clear-all and selective deletion."""

    @pytest.mark.anyio
    async def test_no_body_deletes_all_returns_204(self, client):
        """DELETE /notifications with no body → deletes ALL user notifications → 204."""
        try:
            payload, uid = _override_auth("MEMBER")
            with (
                patch(f"{_EP}.check_rate_limit", new_callable=AsyncMock, return_value=True),
                patch(
                    "app.repositories.notification_repo.bulk_delete",
                    new_callable=AsyncMock,
                    return_value=5,
                ) as mock_bulk,
            ):
                resp = await client.delete(
                    "/api/v1/notifications",
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 204
                mock_bulk.assert_awaited_once_with(uuid.UUID(uid), None)
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_empty_list_deletes_all_returns_204(self, client):
        """DELETE /notifications with empty notification_ids → deletes ALL → 204."""
        try:
            payload, uid = _override_auth("MEMBER")
            with (
                patch(f"{_EP}.check_rate_limit", new_callable=AsyncMock, return_value=True),
                patch(
                    "app.repositories.notification_repo.bulk_delete",
                    new_callable=AsyncMock,
                    return_value=3,
                ) as mock_bulk,
            ):
                resp = await client.request(
                    "DELETE",
                    "/api/v1/notifications",
                    json={"notification_ids": []},
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 204
                mock_bulk.assert_awaited_once_with(uuid.UUID(uid), None)
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_null_notification_ids_deletes_all_returns_204(self, client):
        """DELETE /notifications with notification_ids: null → deletes ALL → 204."""
        try:
            payload, uid = _override_auth("MEMBER")
            with (
                patch(f"{_EP}.check_rate_limit", new_callable=AsyncMock, return_value=True),
                patch(
                    "app.repositories.notification_repo.bulk_delete",
                    new_callable=AsyncMock,
                    return_value=2,
                ) as mock_bulk,
            ):
                resp = await client.request(
                    "DELETE",
                    "/api/v1/notifications",
                    json={"notification_ids": None},
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 204
                mock_bulk.assert_awaited_once_with(uuid.UUID(uid), None)
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_valid_ids_deletes_selective_returns_204(self, client):
        """DELETE /notifications with valid notification_ids → deletes only those → 204."""
        notif_ids = [str(uuid.uuid4()), str(uuid.uuid4())]
        try:
            payload, uid = _override_auth("MEMBER")
            with (
                patch(f"{_EP}.check_rate_limit", new_callable=AsyncMock, return_value=True),
                patch(
                    "app.repositories.notification_repo.bulk_delete",
                    new_callable=AsyncMock,
                    return_value=2,
                ) as mock_bulk,
            ):
                resp = await client.request(
                    "DELETE",
                    "/api/v1/notifications",
                    json={"notification_ids": notif_ids},
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 204
                called_ids = mock_bulk.call_args[0][1]
                assert called_ids == [uuid.UUID(nid) for nid in notif_ids]
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
