"""Tests for tasks endpoint — pending, success, ownership verification, and Redis config."""

import sys
import types
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

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

    with patch.dict(
        sys.modules,
        {
            "celery": celery_mod,
            "celery.result": celery_result_mod,
            "app.celery_app": celery_app_mod,
        },
    ):
        yield celery_result_mod


class TestRedisTimeoutConfig:
    """Verify that init_redis passes the required timeout parameters."""

    def test_redis_from_url_called_with_timeout_params(self) -> None:
        """init_redis must configure socket_timeout, socket_connect_timeout, retry_on_timeout."""
        import inspect

        from app.core import redis as redis_module

        source = inspect.getsource(redis_module.init_redis)
        assert "socket_timeout" in source, "socket_timeout must be set in init_redis"
        assert (
            "socket_connect_timeout" in source
        ), "socket_connect_timeout must be set in init_redis"
        assert "retry_on_timeout" in source, "retry_on_timeout must be set in init_redis"
        assert "max_connections" in source, "max_connections must be set in init_redis"

    def test_redis_timeout_values_are_reasonable(self) -> None:
        """socket_timeout should be >=5s and socket_connect_timeout >=3s (source inspection)."""
        import ast
        import inspect

        from app.core import redis as redis_module

        source = inspect.getsource(redis_module.init_redis)
        # Parse the source to find keyword arguments in the Redis.from_url call
        tree = ast.parse(source)
        kw_values: dict[str, object] = {}
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                for kw in node.keywords:
                    if isinstance(kw.value, ast.Constant):
                        kw_values[kw.arg] = kw.value.value

        socket_timeout = kw_values.get("socket_timeout")
        socket_connect_timeout = kw_values.get("socket_connect_timeout")
        assert (
            isinstance(socket_timeout, (int, float)) and socket_timeout >= 5
        ), f"socket_timeout should be at least 5s, got {socket_timeout}"
        assert (
            isinstance(socket_connect_timeout, (int, float)) and socket_connect_timeout >= 3
        ), f"socket_connect_timeout should be at least 3s, got {socket_connect_timeout}"


class TestTaskStatus:
    @pytest.mark.anyio
    async def test_task_pending(self, client, _mock_celery):
        """GET /tasks/{id}/status → 200 with PENDING state."""
        mock_result = MagicMock()
        mock_result.state = "PENDING"
        mock_result.result = None

        _mock_celery.AsyncResult = MagicMock(return_value=mock_result)

        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=None)

        try:
            _override_auth("ADMIN")
            with patch("app.core.redis.get_redis", return_value=mock_redis):
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

        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=None)

        try:
            _override_auth("ADMIN")
            with patch("app.core.redis.get_redis", return_value=mock_redis):
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

    @pytest.mark.anyio
    async def test_task_status_allowed_for_member(self, client, _mock_celery):
        """GET /tasks/{id}/status -> 200 for MEMBER users who own the task."""
        mock_result = MagicMock()
        mock_result.state = "PENDING"
        mock_result.result = None

        _mock_celery.AsyncResult = MagicMock(return_value=mock_result)

        try:
            # Capture the user ID so Redis can return it as the task owner
            _, uid = _override_auth("MEMBER")
            mock_redis = AsyncMock()
            mock_redis.get = AsyncMock(return_value=uid)
            with patch("app.core.redis.get_redis", return_value=mock_redis):
                resp = await client.get(
                    "/api/v1/tasks/task-789/status",
                    headers={"Authorization": "Bearer fake"},
                )
            assert resp.status_code == 200
            data = resp.json()
            assert data["status"] == "PENDING"
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_task_status_requires_authentication(self, unauthed_client, _mock_celery):
        """GET /tasks/{id}/status -> 401 for unauthenticated requests."""
        resp = await unauthed_client.get("/api/v1/tasks/task-000/status")
        assert resp.status_code == 401

    @pytest.mark.anyio
    async def test_task_status_forbidden_for_guest(self, client, _mock_celery):
        """GET /tasks/{id}/status -> 403 for GUEST users (requires MEMBER or above)."""
        try:
            _override_auth("GUEST")
            resp = await client.get(
                "/api/v1/tasks/task-guest-001/status",
                headers={"Authorization": "Bearer fake"},
            )
            assert resp.status_code == 403
        finally:
            _clear_overrides()


class TestTaskOwnership:
    """Verify that MEMBER users can only access their own tasks."""

    @pytest.mark.anyio
    async def test_member_can_access_own_task(self, client, _mock_celery):
        """MEMBER who owns the task gets 200."""
        owner_id = str(uuid.uuid4())

        mock_result = MagicMock()
        mock_result.state = "SUCCESS"
        mock_result.result = {"download_url": "https://example.com/my-export.csv"}
        _mock_celery.AsyncResult = MagicMock(return_value=mock_result)

        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=owner_id)

        try:
            _override_auth("MEMBER", user_id=owner_id)
            with patch("app.core.redis.get_redis", return_value=mock_redis):
                resp = await client.get(
                    "/api/v1/tasks/task-own-001/status",
                    headers={"Authorization": "Bearer fake"},
                )
            assert resp.status_code == 200
            data = resp.json()
            assert data["download_url"] == "https://example.com/my-export.csv"
            mock_redis.get.assert_awaited_once_with("task_owner:task-own-001")
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_member_cannot_access_other_users_task(self, client, _mock_celery):
        """MEMBER gets 403 when accessing another user's task."""
        owner_id = str(uuid.uuid4())
        other_user_id = str(uuid.uuid4())

        mock_result = MagicMock()
        mock_result.state = "SUCCESS"
        mock_result.result = {"download_url": "https://example.com/secret.csv"}
        _mock_celery.AsyncResult = MagicMock(return_value=mock_result)

        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=owner_id)

        try:
            _override_auth("MEMBER", user_id=other_user_id)
            with patch("app.core.redis.get_redis", return_value=mock_redis):
                resp = await client.get(
                    "/api/v1/tasks/task-other-001/status",
                    headers={"Authorization": "Bearer fake"},
                )
            assert resp.status_code == 403
            assert "do not have access" in resp.json()["detail"]["message"]
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_admin_can_access_any_task(self, client, _mock_celery):
        """ADMIN can access any task regardless of ownership."""
        owner_id = str(uuid.uuid4())

        mock_result = MagicMock()
        mock_result.state = "SUCCESS"
        mock_result.result = {"download_url": "https://example.com/any-export.csv"}
        _mock_celery.AsyncResult = MagicMock(return_value=mock_result)

        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=owner_id)

        try:
            # ADMIN with different user_id than the task owner
            _override_auth("ADMIN", user_id=str(uuid.uuid4()))
            with patch("app.core.redis.get_redis", return_value=mock_redis):
                resp = await client.get(
                    "/api/v1/tasks/task-admin-001/status",
                    headers={"Authorization": "Bearer fake"},
                )
            assert resp.status_code == 200
            data = resp.json()
            assert data["download_url"] == "https://example.com/any-export.csv"
            # Redis should NOT be queried for ADMIN
            mock_redis.get.assert_not_awaited()
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_super_admin_can_access_any_task(self, client, _mock_celery):
        """SUPER_ADMIN can access any task regardless of ownership."""
        owner_id = str(uuid.uuid4())

        mock_result = MagicMock()
        mock_result.state = "SUCCESS"
        mock_result.result = {"download_url": "https://example.com/sa-export.csv"}
        _mock_celery.AsyncResult = MagicMock(return_value=mock_result)

        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=owner_id)

        try:
            _override_auth("SUPER_ADMIN", user_id=str(uuid.uuid4()))
            with patch("app.core.redis.get_redis", return_value=mock_redis):
                resp = await client.get(
                    "/api/v1/tasks/task-sa-001/status",
                    headers={"Authorization": "Bearer fake"},
                )
            assert resp.status_code == 200
            # Redis should NOT be queried for SUPER_ADMIN
            mock_redis.get.assert_not_awaited()
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_member_access_task_without_ownership_record(self, client, _mock_celery):
        """MEMBER gets 403 when ownership record is missing (fail closed for security)."""
        mock_result = MagicMock()
        mock_result.state = "PENDING"
        mock_result.result = None
        _mock_celery.AsyncResult = MagicMock(return_value=mock_result)

        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=None)

        try:
            _override_auth("MEMBER")
            with patch("app.core.redis.get_redis", return_value=mock_redis):
                resp = await client.get(
                    "/api/v1/tasks/task-noowner-001/status",
                    headers={"Authorization": "Bearer fake"},
                )
            # No ownership record → fail closed (403)
            assert resp.status_code == 403
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_nonexistent_task_returns_pending(self, client, _mock_celery):
        """MEMBER with task ownership returns PENDING for non-existent task IDs."""
        mock_result = MagicMock()
        mock_result.state = "PENDING"
        mock_result.result = None
        _mock_celery.AsyncResult = MagicMock(return_value=mock_result)

        try:
            # Capture UID so Redis can confirm task ownership
            _, uid = _override_auth("MEMBER")
            mock_redis = AsyncMock()
            mock_redis.get = AsyncMock(return_value=uid)
            with patch("app.core.redis.get_redis", return_value=mock_redis):
                resp = await client.get(
                    f"/api/v1/tasks/{uuid.uuid4()}/status",
                    headers={"Authorization": "Bearer fake"},
                )
            assert resp.status_code == 200
            assert resp.json()["status"] == "PENDING"
            assert resp.json()["download_url"] is None
        finally:
            _clear_overrides()
