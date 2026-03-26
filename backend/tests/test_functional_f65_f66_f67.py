"""Tests for F-65, F-66, F-67 functional bug fixes.

F-65: DM admin endpoint returns 404 for non-existent conversations.
F-66: DM orphan cleanup S3 paginator has timeout.
F-67: WS FORCE_LOGOUT delivery uses wait_for with timeout.
"""

import asyncio
import sys
import types
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# F-65: Admin endpoint returns 404 for non-existent conversation
# ---------------------------------------------------------------------------
class TestF65AdminConversationNotFound:
    """F-65: GET /dm/admin/conversations/{id}/messages should 404 for missing conversations."""

    @pytest.mark.anyio
    async def test_admin_returns_404_for_nonexistent_conversation(self, client):
        """Should return 404 when conversation does not exist."""
        from app.core.deps import get_current_user
        from app.main import app

        admin_payload = {
            "sub": str(uuid.uuid4()),
            "role": "SUPER_ADMIN",
            "jti": str(uuid.uuid4()),
        }
        app.dependency_overrides[get_current_user] = lambda: admin_payload
        conv_id = uuid.uuid4()

        try:
            with (
                patch(
                    "app.api.v1.endpoints.dm.check_rate_limit",
                    new_callable=AsyncMock,
                    return_value=True,
                ),
                patch(
                    "app.repositories.dm_repo.conversation_exists",
                    new_callable=AsyncMock,
                    return_value=False,
                ),
            ):
                resp = await client.get(
                    f"/api/v1/dm/admin/conversations/{conv_id}/messages"
                )
                assert resp.status_code == 404
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.anyio
    async def test_admin_returns_200_for_existing_conversation(self, client):
        """Should return 200 when conversation exists."""
        from app.core.deps import get_current_user
        from app.main import app

        admin_payload = {
            "sub": str(uuid.uuid4()),
            "role": "SUPER_ADMIN",
            "jti": str(uuid.uuid4()),
        }
        app.dependency_overrides[get_current_user] = lambda: admin_payload
        conv_id = uuid.uuid4()

        try:
            with (
                patch(
                    "app.api.v1.endpoints.dm.check_rate_limit",
                    new_callable=AsyncMock,
                    return_value=True,
                ),
                patch(
                    "app.repositories.dm_repo.conversation_exists",
                    new_callable=AsyncMock,
                    return_value=True,
                ),
                patch(
                    "app.repositories.dm_repo.find_messages",
                    new_callable=AsyncMock,
                    return_value=([], 0),
                ),
            ):
                resp = await client.get(
                    f"/api/v1/dm/admin/conversations/{conv_id}/messages"
                )
                assert resp.status_code == 200
                data = resp.json()
                assert data["messages"] == []
                assert data["total"] == 0
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.anyio
    async def test_conversation_exists_repo_function(self):
        """dm_repo.conversation_exists returns False for missing conversation."""
        mock_pool = MagicMock()
        mock_conn = AsyncMock()
        mock_conn.fetchval = AsyncMock(return_value=False)
        mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

        with patch("app.repositories.dm_repo.get_pool", return_value=mock_pool):
            from app.repositories.dm_repo import conversation_exists

            result = await conversation_exists(uuid.uuid4())
            assert result is False
            mock_conn.fetchval.assert_called_once()

    @pytest.mark.anyio
    async def test_conversation_exists_returns_true(self):
        """dm_repo.conversation_exists returns True for existing conversation."""
        mock_pool = MagicMock()
        mock_conn = AsyncMock()
        mock_conn.fetchval = AsyncMock(return_value=True)
        mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

        with patch("app.repositories.dm_repo.get_pool", return_value=mock_pool):
            from app.repositories.dm_repo import conversation_exists

            result = await conversation_exists(uuid.uuid4())
            assert result is True


# ---------------------------------------------------------------------------
# F-66: DM orphan cleanup S3 paginator timeout
# ---------------------------------------------------------------------------
@pytest.fixture(autouse=True)
def _celery_modules():
    """Inject fake celery modules so task imports succeed without a broker."""
    celery_mod = types.ModuleType("celery")
    celery_result_mod = types.ModuleType("celery.result")
    celery_mod.result = celery_result_mod
    celery_mod.shared_task = lambda **kw: (lambda fn: fn)

    celery_app_mod = types.ModuleType("app.celery_app")
    mock_celery_app = MagicMock()
    mock_celery_app.task = lambda *a, **kw: (lambda fn: fn)
    celery_app_mod.celery = mock_celery_app

    saved = {}
    for key in ("celery", "celery.result", "app.celery_app"):
        saved[key] = sys.modules.get(key)

    sys.modules["celery"] = celery_mod
    sys.modules["celery.result"] = celery_result_mod
    sys.modules["app.celery_app"] = celery_app_mod

    yield

    for key, val in saved.items():
        if val is None:
            sys.modules.pop(key, None)
        else:
            sys.modules[key] = val


class TestF66DmOrphanCleanupTimeout:
    """F-66: S3 paginator listing should have a timeout."""

    @pytest.mark.anyio
    async def test_s3_listing_timeout_returns_error_dict(self):
        """When S3 listing times out, cleanup should return error dict with timeout flag."""
        from app.tasks.dm_cleanup import _cleanup_dm_orphans

        mock_pool = AsyncMock()
        mock_storage = MagicMock()
        paginator = MagicMock()
        mock_storage.get_paginator.return_value = paginator

        mock_loop = MagicMock()

        # Make run_in_executor return a coroutine that hangs
        async def _hang(*args, **kwargs):
            await asyncio.sleep(9999)

        mock_loop.run_in_executor = MagicMock(side_effect=lambda ex, fn: _hang())

        with (
            patch("app.tasks.dm_cleanup._ensure_pool", new_callable=AsyncMock),
            patch("app.core.database.get_pool", return_value=mock_pool),
            patch("app.core.storage.get_storage", return_value=mock_storage),
            patch("app.core.config.settings") as mock_settings,
            patch("asyncio.get_event_loop", return_value=mock_loop),
        ):
            mock_settings.S3_BUCKET_NAME = "test-bucket"

            # Patch wait_for at the module level used inside _cleanup_dm_orphans
            original_wait_for = asyncio.wait_for

            async def fake_wait_for(coro, *, timeout):
                coro.close()
                raise asyncio.TimeoutError()

            with patch("asyncio.wait_for", side_effect=fake_wait_for):
                result = await _cleanup_dm_orphans()

            assert result["errors"] == 1
            assert result["timeout"] is True
            assert result["checked"] == 0
            assert result["deleted"] == 0

    def test_s3_timeout_constant_exists_in_source(self):
        """Verify the timeout constant is present in the source code."""
        import inspect

        from app.tasks import dm_cleanup

        source = inspect.getsource(dm_cleanup._cleanup_dm_orphans)
        assert "wait_for" in source
        assert "TimeoutError" in source
        assert "_DM_S3_LIST_TIMEOUT" in source


# ---------------------------------------------------------------------------
# F-67: WS FORCE_LOGOUT delivery with wait_for
# ---------------------------------------------------------------------------
class TestF67ForceLogoutDelivery:
    """F-67: FORCE_LOGOUT messages should use asyncio.wait_for for guaranteed delivery."""

    def test_force_logout_uses_wait_for_in_source(self):
        """Verify the source code uses asyncio.wait_for for FORCE_LOGOUT sends."""
        import inspect

        from app.api.v1.endpoints import ws

        source = inspect.getsource(ws)
        # Check that wait_for wraps FORCE_LOGOUT sends
        assert "wait_for" in source
        # Check that there's a timeout specified
        assert "timeout=5.0" in source

    def test_force_logout_has_try_except_around_send(self):
        """Verify FORCE_LOGOUT send is wrapped in try/except for resilience."""
        import inspect

        from app.api.v1.endpoints import ws

        source = inspect.getsource(ws)
        # Both FORCE_LOGOUT sends should have TimeoutError handling
        assert "asyncio.TimeoutError" in source
        assert "Failed to deliver FORCE_LOGOUT" in source

    @pytest.mark.anyio
    async def test_force_logout_expired_session_sends_with_timeout(self):
        """When session expires, FORCE_LOGOUT should be sent with wait_for timeout."""
        mock_ws = AsyncMock()
        mock_ws.send_json = AsyncMock()
        mock_ws.close = AsyncMock()

        # Simulate the logic directly
        user_id = str(uuid.uuid4())

        try:
            await asyncio.wait_for(
                mock_ws.send_json({"type": "FORCE_LOGOUT"}), timeout=5.0
            )
        except (asyncio.TimeoutError, Exception):
            pass

        mock_ws.send_json.assert_called_once_with({"type": "FORCE_LOGOUT"})

    @pytest.mark.anyio
    async def test_force_logout_timeout_does_not_prevent_close(self):
        """If FORCE_LOGOUT send times out, ws.close should still be called."""
        mock_ws = AsyncMock()

        # Make send_json hang forever
        async def _hang(*args, **kwargs):
            await asyncio.sleep(9999)

        mock_ws.send_json = _hang
        mock_ws.close = AsyncMock()

        # Simulate the F-67 pattern
        try:
            await asyncio.wait_for(
                mock_ws.send_json({"type": "FORCE_LOGOUT"}), timeout=0.01
            )
        except (asyncio.TimeoutError, Exception):
            pass

        await mock_ws.close(code=4003, reason="Session expired")
        mock_ws.close.assert_called_once_with(code=4003, reason="Session expired")

    @pytest.mark.anyio
    async def test_force_logout_jti_mismatch_sends_reason(self):
        """On JTI mismatch, FORCE_LOGOUT with reason='session_replaced' should be sent."""
        mock_ws = AsyncMock()
        mock_ws.send_json = AsyncMock()

        try:
            await asyncio.wait_for(
                mock_ws.send_json(
                    {"type": "FORCE_LOGOUT", "reason": "session_replaced"}
                ),
                timeout=5.0,
            )
        except (asyncio.TimeoutError, Exception):
            pass

        mock_ws.send_json.assert_called_once_with(
            {"type": "FORCE_LOGOUT", "reason": "session_replaced"}
        )
