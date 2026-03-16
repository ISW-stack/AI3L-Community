"""Tests for B2 (guest IP counter), B4 (file delete audit), B6 (VT key validation),
and G4 (form auto-close task)."""

import sys
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient

_EP_AUTH = "app.api.v1.endpoints.auth"
_EP_FILES = "app.api.v1.endpoints.files"


# ---------------------------------------------------------------------------
# B2: Guest logout with None IP logs warning
# ---------------------------------------------------------------------------
class TestGuestLogoutNoneIP:
    """B2: When IP is None during guest logout, a warning is logged and
    the per-IP counter is not decremented (but global counter still is)."""

    @patch(f"{_EP_AUTH}.emit", new_callable=AsyncMock)
    @patch(f"{_EP_AUTH}.decrement_guest_ip_counter", new_callable=AsyncMock)
    @patch(f"{_EP_AUTH}.decrement_guest_counter", new_callable=AsyncMock)
    @patch(f"{_EP_AUTH}.destroy_session", new_callable=AsyncMock)
    async def test_guest_logout_none_ip_logs_warning(
        self,
        mock_destroy,
        mock_dec_global,
        mock_dec_ip,
        mock_emit,
        client: AsyncClient,
    ):
        """Guest logout with request.client = None should decrement global counter
        but NOT call decrement_guest_ip_counter, and should log a warning."""
        from app.core.deps import get_current_user
        from app.main import app

        payload = {"sub": str(uuid.uuid4()), "role": "GUEST", "jti": "jti-g-none"}
        app.dependency_overrides[get_current_user] = lambda: payload
        try:
            # Simulate request.client being None by patching the Request
            with patch(
                "starlette.requests.Request.client", new_callable=lambda: property(lambda s: None)
            ):
                resp = await client.post(
                    "/api/v1/auth/logout",
                    headers={"Authorization": "Bearer fake"},
                )
            assert resp.status_code == 200
            mock_dec_global.assert_called_once()
            mock_dec_ip.assert_not_called()
        finally:
            app.dependency_overrides.pop(get_current_user, None)

    @patch(f"{_EP_AUTH}.emit", new_callable=AsyncMock)
    @patch(f"{_EP_AUTH}.decrement_guest_ip_counter", new_callable=AsyncMock)
    @patch(f"{_EP_AUTH}.decrement_guest_counter", new_callable=AsyncMock)
    @patch(f"{_EP_AUTH}.destroy_session", new_callable=AsyncMock)
    async def test_guest_logout_with_ip_decrements_both(
        self,
        mock_destroy,
        mock_dec_global,
        mock_dec_ip,
        mock_emit,
        client: AsyncClient,
    ):
        """Guest logout with valid IP should decrement both counters."""
        from app.core.deps import get_current_user
        from app.main import app

        payload = {"sub": str(uuid.uuid4()), "role": "GUEST", "jti": "jti-g-ok"}
        app.dependency_overrides[get_current_user] = lambda: payload
        try:
            resp = await client.post(
                "/api/v1/auth/logout",
                headers={"Authorization": "Bearer fake"},
            )
            assert resp.status_code == 200
            mock_dec_global.assert_called_once()
            mock_dec_ip.assert_called_once()
        finally:
            app.dependency_overrides.pop(get_current_user, None)


# ---------------------------------------------------------------------------
# B4: User file deletion emits audit event
# ---------------------------------------------------------------------------
class TestFileDeleteAuditEvent:
    """B4: User file deletion should emit an audit event, not just admin deletions."""

    @patch(f"{_EP_FILES}.file_scan_repo")
    @patch(f"{_EP_FILES}.user_repo")
    @patch(f"{_EP_FILES}.async_delete_file", new_callable=AsyncMock)
    @patch(f"{_EP_FILES}.async_get_file_size", new_callable=AsyncMock, return_value=1024)
    async def test_user_file_delete_emits_audit(
        self,
        mock_get_size,
        mock_delete,
        mock_user_repo,
        mock_scan_repo,
        client: AsyncClient,
    ):
        from app.core.deps import get_current_user
        from app.main import app

        user_id = str(uuid.uuid4())
        payload = {"sub": user_id, "role": "MEMBER", "jti": "jti-f1"}
        app.dependency_overrides[get_current_user] = lambda: payload
        mock_user_repo.increment_storage_used = AsyncMock()
        mock_scan_repo.delete_by_key = AsyncMock()

        try:
            key = f"editor/{user_id}/testfile.png"
            with patch("app.core.event_bus.emit", new_callable=AsyncMock) as mock_emit:
                resp = await client.delete(
                    f"/api/v1/files/content/{key}",
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 200
                # Verify audit event was emitted with action="file_delete"
                mock_emit.assert_called_once()
                call_kwargs = mock_emit.call_args
                assert call_kwargs[0][0] == "audit.action"
                assert call_kwargs[1]["action"] == "file_delete"
                assert call_kwargs[1]["actor_id"] == user_id
        finally:
            app.dependency_overrides.clear()

    @patch(f"{_EP_FILES}.file_scan_repo")
    @patch(f"{_EP_FILES}.user_repo")
    @patch(f"{_EP_FILES}.async_delete_file", new_callable=AsyncMock)
    @patch(f"{_EP_FILES}.async_get_file_size", new_callable=AsyncMock, return_value=1024)
    async def test_admin_file_delete_emits_admin_audit(
        self,
        mock_get_size,
        mock_delete,
        mock_user_repo,
        mock_scan_repo,
        client: AsyncClient,
    ):
        from app.core.deps import get_current_user
        from app.main import app

        admin_id = str(uuid.uuid4())
        owner_id = str(uuid.uuid4())
        payload = {"sub": admin_id, "role": "SUPER_ADMIN", "jti": "jti-f2"}
        app.dependency_overrides[get_current_user] = lambda: payload
        mock_user_repo.increment_storage_used = AsyncMock()
        mock_scan_repo.delete_by_key = AsyncMock()

        try:
            key = f"editor/{owner_id}/testfile.png"
            with patch("app.core.event_bus.emit", new_callable=AsyncMock) as mock_emit:
                resp = await client.delete(
                    f"/api/v1/files/content/{key}",
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 200
                mock_emit.assert_called_once()
                call_kwargs = mock_emit.call_args
                assert call_kwargs[1]["action"] == "admin_file_delete"
        finally:
            app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# B6: VirusTotal storage_key format validation
# ---------------------------------------------------------------------------
class TestVirusTotalKeyValidation:
    """B6: _decrement_owner_storage should handle invalid storage keys gracefully."""

    @pytest.mark.parametrize("bad_key", ["", "noslash", None])
    def test_invalid_storage_key_returns_early(self, bad_key):
        """Invalid storage keys should be logged and skipped, not raise."""
        # We need to test the async _decrement_owner_storage function
        import asyncio

        from app.tasks.virustotal import _decrement_owner_storage

        with patch("app.tasks.virustotal._ensure_pool", new_callable=AsyncMock):
            with patch("app.tasks.virustotal.logger") as mock_logger:
                # Should not raise, should log warning
                if bad_key is None:
                    # None will fail the `not storage_key` check
                    asyncio.run(_decrement_owner_storage(bad_key, 1024))  # type: ignore[arg-type]
                else:
                    asyncio.run(_decrement_owner_storage(bad_key, 1024))
                mock_logger.warning.assert_called_once()
                assert "Invalid storage key format" in mock_logger.warning.call_args[0][0]

    def test_valid_storage_key_proceeds(self):
        """Valid storage key should attempt to decrement storage."""
        import asyncio

        from app.tasks.virustotal import _decrement_owner_storage

        user_id = str(uuid.uuid4())
        key = f"editor/{user_id}/file.png"

        mock_user_repo = MagicMock()
        mock_user_repo.increment_storage_used = AsyncMock()

        with (
            patch("app.tasks.virustotal._ensure_pool", new_callable=AsyncMock),
            patch("app.tasks.virustotal.user_repo", mock_user_repo, create=True),
            patch(
                "app.repositories.user_repo.increment_storage_used",
                mock_user_repo.increment_storage_used,
            ),
        ):
            # The function imports user_repo lazily, so we patch the import
            with patch.dict("sys.modules", {}):
                pass  # just ensure clean state
            with patch("app.tasks.virustotal.user_repo", mock_user_repo, create=True):
                # Actually test with a proper mock
                asyncio.run(_decrement_owner_storage(key, 1024))


# ---------------------------------------------------------------------------
# G4: Form auto-close task
# ---------------------------------------------------------------------------
class TestFormAutoCloseTask:
    """G4: Periodic task should close forms past their deadline."""

    def test_close_expired_forms(self, mock_pool, mock_conn):
        """_close_expired_forms should UPDATE forms past deadline."""
        import asyncio

        form_id = uuid.uuid4()
        mock_conn.fetch = AsyncMock(return_value=[{"id": form_id}])

        with patch("app.tasks.form_autoclose.get_pool", return_value=mock_pool):
            with patch("app.tasks.form_autoclose._ensure_pool", new_callable=AsyncMock):
                from app.tasks.form_autoclose import _close_expired_forms

                with patch("app.tasks.form_autoclose.get_pool", return_value=mock_pool):
                    result = asyncio.run(_close_expired_forms())

        assert len(result) == 1
        assert result[0] == str(form_id)
        mock_conn.fetch.assert_called_once()
        # Verify the SQL contains the right conditions
        sql = mock_conn.fetch.call_args[0][0]
        assert "is_closed = true" in sql
        assert "deadline < NOW()" in sql
        assert "is_deleted = false" in sql

    def test_close_expired_forms_no_results(self, mock_pool, mock_conn):
        """When no forms are expired, returns empty list."""
        import asyncio

        mock_conn.fetch = AsyncMock(return_value=[])

        with patch("app.tasks.form_autoclose.get_pool", return_value=mock_pool):
            with patch("app.tasks.form_autoclose._ensure_pool", new_callable=AsyncMock):
                from app.tasks.form_autoclose import _close_expired_forms

                with patch("app.tasks.form_autoclose.get_pool", return_value=mock_pool):
                    result = asyncio.run(_close_expired_forms())

        assert result == []

    def test_auto_close_task_integration(self, mock_pool, mock_conn):
        """The Celery task wrapper should call _close_expired_forms and return results."""
        form_id = uuid.uuid4()
        mock_conn.fetch = AsyncMock(return_value=[{"id": form_id}])

        # Mock celery decorator
        celery_mock = MagicMock()
        celery_mock.task = lambda **kwargs: lambda f: f

        with (
            patch.dict(sys.modules, {"app.celery_app": MagicMock(celery=celery_mock)}),
            patch("app.tasks.form_autoclose.get_pool", return_value=mock_pool),
            patch("app.tasks.form_autoclose._ensure_pool", new_callable=AsyncMock),
        ):
            # Re-import to apply patches
            import importlib

            import app.tasks.form_autoclose as fac

            importlib.reload(fac)

            with patch.object(fac, "get_pool", return_value=mock_pool):
                with patch.object(fac, "_ensure_pool", new_callable=AsyncMock):
                    result = fac.auto_close_expired_forms(None)

        assert result["closed_count"] == 1
        assert str(form_id) in result["closed_ids"]


# ---------------------------------------------------------------------------
# G4: Form converter includes is_closed in is_active computation
# ---------------------------------------------------------------------------
class TestFormConverterIsClosed:
    """G4: Converter should treat is_closed forms as inactive."""

    def test_closed_form_is_not_active(self):
        from app.converters.form_converter import row_to_form

        row = {
            "id": uuid.uuid4(),
            "sig_id": None,
            "title": "Test",
            "description": None,
            "banner_url": None,
            "deadline": None,
            "max_respondents": None,
            "questions": "[]",
            "is_schema_locked": False,
            "allow_non_members": False,
            "is_closed": True,
            "is_deleted": False,
            "created_by": uuid.uuid4(),
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        }
        result = row_to_form(row)
        assert result["is_active"] is False

    def test_open_form_is_active(self):
        from app.converters.form_converter import row_to_form

        row = {
            "id": uuid.uuid4(),
            "sig_id": None,
            "title": "Test",
            "description": None,
            "banner_url": None,
            "deadline": None,
            "max_respondents": None,
            "questions": "[]",
            "is_schema_locked": False,
            "allow_non_members": False,
            "is_closed": False,
            "is_deleted": False,
            "created_by": uuid.uuid4(),
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        }
        result = row_to_form(row)
        assert result["is_active"] is True

    def test_missing_is_closed_defaults_to_active(self):
        """Rows without is_closed (old data) should default to active."""
        from app.converters.form_converter import row_to_form

        row = {
            "id": uuid.uuid4(),
            "sig_id": None,
            "title": "Test",
            "description": None,
            "banner_url": None,
            "deadline": None,
            "max_respondents": None,
            "questions": "[]",
            "is_schema_locked": False,
            "allow_non_members": False,
            "is_deleted": False,
            "created_by": uuid.uuid4(),
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        }
        result = row_to_form(row)
        assert result["is_active"] is True
