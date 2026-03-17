"""Tests for read_all_notifications rate limit (N2 fix)."""

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


class TestReadAllNotificationsRateLimit:
    @pytest.mark.anyio
    async def test_read_all_rate_limited_returns_429(self, client):
        """PUT /notifications/read-all → 429 when rate limited."""
        try:
            _override_auth("MEMBER")
            with patch(f"{_EP}.check_rate_limit", new_callable=AsyncMock, return_value=False):
                resp = await client.put(
                    "/api/v1/notifications/read-all",
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 429
                assert "too many" in resp.json()["detail"]["message"].lower()
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_read_all_passes_when_not_rate_limited(self, client):
        """PUT /notifications/read-all → 200 when rate limit OK."""
        try:
            _override_auth("MEMBER")
            with (
                patch(f"{_EP}.check_rate_limit", new_callable=AsyncMock, return_value=True),
                patch(f"{_EP}.mark_all_as_read", new_callable=AsyncMock, return_value=3),
            ):
                resp = await client.put(
                    "/api/v1/notifications/read-all",
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 200
                assert "3" in resp.json()["message"]
        finally:
            _clear_overrides()
