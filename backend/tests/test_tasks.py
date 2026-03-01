"""Tests for tasks endpoint — pending, success."""

import sys
import types
import uuid
from unittest.mock import MagicMock, patch

import pytest


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


@pytest.fixture(autouse=True)
def _mock_celery():
    """Pre-populate sys.modules so 'from celery.result import AsyncResult' works."""
    celery_mod = types.ModuleType("celery")
    celery_result_mod = types.ModuleType("celery.result")
    celery_mod.result = celery_result_mod

    celery_app_mod = types.ModuleType("app.celery_app")
    celery_app_mod.celery = MagicMock()

    with patch.dict(sys.modules, {
        "celery": celery_mod,
        "celery.result": celery_result_mod,
        "app.celery_app": celery_app_mod,
    }):
        yield celery_result_mod


class TestTaskStatus:
    @pytest.mark.anyio
    async def test_task_pending(self, client, _mock_celery):
        """GET /tasks/{id}/status → 200 with PENDING state."""
        mock_result = MagicMock()
        mock_result.state = "PENDING"
        mock_result.result = None

        _mock_celery.AsyncResult = MagicMock(return_value=mock_result)

        try:
            _override_auth("MEMBER")
            resp = await client.get(
                "/api/v1/tasks/task-123/status",
                headers={"Authorization": "Bearer fake"},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["status"] == "PENDING"
            assert data["download_url"] is None
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_task_success(self, client, _mock_celery):
        """GET /tasks/{id}/status → 200 with SUCCESS state and download URL."""
        mock_result = MagicMock()
        mock_result.state = "SUCCESS"
        mock_result.result = {"download_url": "https://example.com/file.csv"}

        _mock_celery.AsyncResult = MagicMock(return_value=mock_result)

        try:
            _override_auth("MEMBER")
            resp = await client.get(
                "/api/v1/tasks/task-456/status",
                headers={"Authorization": "Bearer fake"},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["status"] == "SUCCESS"
            assert data["download_url"] == "https://example.com/file.csv"
        finally:
            _clear_overrides()
