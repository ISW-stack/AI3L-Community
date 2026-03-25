"""Tests for site data export endpoints and task logic."""

import json
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

_EP = "app.api.v1.endpoints.export"
_REDIS = "app.core.redis.get_redis"
_RATE_LIMIT = "app.core.rate_limit.check_rate_limit"
_STORAGE = "app.core.storage.get_storage"
_PRESIGN = "app.core.storage.generate_presigned_url"
_EMIT = "app.core.event_bus.emit"


def _override_auth(role="SUPER_ADMIN", user_id=None):
    from app.core.deps import get_current_user
    from app.main import app

    uid = user_id or str(uuid.uuid4())
    payload = {"sub": uid, "role": role, "jti": str(uuid.uuid4())}
    app.dependency_overrides[get_current_user] = lambda: payload
    return payload, uid


def _clear_overrides():
    from app.main import app

    app.dependency_overrides.clear()


# ── POST /admin/export ────────────────────────────────────────────────────


class TestStartExport:
    @pytest.mark.anyio
    async def test_start_export_super_admin(self, client):
        """POST /admin/export → 202 for SUPER_ADMIN."""
        try:
            _override_auth("SUPER_ADMIN")
            mock_redis = AsyncMock()
            # B2: pre-lock uses SET NX → returns True on success
            mock_redis.set = AsyncMock(return_value=True)

            mock_task = MagicMock()
            mock_task.id = "celery-task-123"

            with (
                patch(_RATE_LIMIT, new_callable=AsyncMock, return_value=True),
                patch(_REDIS, return_value=mock_redis),
                patch(
                    "app.tasks.site_export.export_site_data.delay",
                    return_value=mock_task,
                ),
                patch(_EMIT, new_callable=AsyncMock),
            ):
                resp = await client.post(
                    "/api/v1/admin/export",
                    json={"include_database": True, "include_files": True},
                )
                assert resp.status_code == 202
                data = resp.json()
                assert data["task_id"] == "celery-task-123"
                assert "message" in data
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_start_export_admin_forbidden(self, client):
        """POST /admin/export → 403 for ADMIN (not SUPER_ADMIN)."""
        try:
            _override_auth("ADMIN")
            resp = await client.post(
                "/api/v1/admin/export",
                json={"include_database": True, "include_files": False},
            )
            assert resp.status_code == 403
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_start_export_member_forbidden(self, client):
        """POST /admin/export → 403 for MEMBER."""
        try:
            _override_auth("MEMBER")
            resp = await client.post(
                "/api/v1/admin/export",
                json={"include_database": True, "include_files": True},
            )
            assert resp.status_code == 403
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_start_export_rate_limited(self, client):
        """POST /admin/export → 429 when rate limit exceeded."""
        try:
            _override_auth("SUPER_ADMIN")
            mock_redis = AsyncMock()

            with (
                patch(_RATE_LIMIT, new_callable=AsyncMock, return_value=False),
                patch(_REDIS, return_value=mock_redis),
            ):
                resp = await client.post(
                    "/api/v1/admin/export",
                    json={"include_database": True, "include_files": True},
                )
                assert resp.status_code == 429
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_start_export_lock_conflict(self, client):
        """POST /admin/export → 409 when another export is running (SET NX fails)."""
        try:
            _override_auth("SUPER_ADMIN")
            mock_redis = AsyncMock()
            # B2: SET NX returns None/False when lock already held
            mock_redis.set = AsyncMock(return_value=None)

            with (
                patch(_RATE_LIMIT, new_callable=AsyncMock, return_value=True),
                patch(_REDIS, return_value=mock_redis),
            ):
                resp = await client.post(
                    "/api/v1/admin/export",
                    json={"include_database": True, "include_files": True},
                )
                assert resp.status_code == 409
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_start_export_prelock_uses_set_nx(self, client):
        """B2: Endpoint uses atomic SET NX (not GET+check) for lock."""
        try:
            _override_auth("SUPER_ADMIN")
            mock_redis = AsyncMock()
            mock_redis.set = AsyncMock(return_value=True)

            mock_task = MagicMock()
            mock_task.id = "celery-task-456"

            with (
                patch(_RATE_LIMIT, new_callable=AsyncMock, return_value=True),
                patch(_REDIS, return_value=mock_redis),
                patch(
                    "app.tasks.site_export.export_site_data.delay",
                    return_value=mock_task,
                ),
                patch(_EMIT, new_callable=AsyncMock),
            ):
                resp = await client.post(
                    "/api/v1/admin/export",
                    json={"include_database": True, "include_files": True},
                )
                assert resp.status_code == 202
                # Verify SET NX was called with "pending" value and short TTL
                mock_redis.set.assert_any_call("export:site:lock", "pending", nx=True, ex=60)
        finally:
            _clear_overrides()


# ── GET /admin/export/progress/{task_id} ──────────────────────────────────


class TestExportProgress:
    @pytest.mark.anyio
    async def test_progress_pending(self, client):
        """GET /admin/export/progress/{task_id} → progress data for SUPER_ADMIN."""
        try:
            _override_auth("SUPER_ADMIN")
            mock_redis = AsyncMock()
            mock_redis.hgetall = AsyncMock(
                return_value={
                    "phase": "db",
                    "current": "5",
                    "total": "30",
                    "detail": "Exporting table: posts",
                    "zip_size": "0",
                    "started_at": "2026-03-25T14:30:00Z",
                }
            )

            mock_result = MagicMock()
            mock_result.state = "STARTED"
            mock_result.result = None

            with (
                patch(_REDIS, return_value=mock_redis),
                patch("celery.result.AsyncResult", return_value=mock_result),
            ):
                resp = await client.get("/api/v1/admin/export/progress/task-123")
                assert resp.status_code == 200
                data = resp.json()
                assert data["task_id"] == "task-123"
                assert data["status"] == "STARTED"
                assert data["phase"] == "db"
                assert data["current"] == 5
                assert data["total"] == 30
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_progress_success_regenerates_url(self, client):
        """B6: GET progress → regenerates presigned URL from storage_key in Redis."""
        try:
            _override_auth("SUPER_ADMIN")
            mock_redis = AsyncMock()
            mock_redis.hgetall = AsyncMock(
                return_value={
                    "phase": "done",
                    "current": "1",
                    "total": "1",
                    "zip_size": "12345",
                    "storage_key": "exports/site-backup/task-456/abc.zip",
                }
            )

            mock_result = MagicMock()
            mock_result.state = "SUCCESS"
            mock_result.result = {"download_url": "https://old-expired-url.com/export.zip"}

            with (
                patch(_REDIS, return_value=mock_redis),
                patch("celery.result.AsyncResult", return_value=mock_result),
                patch(
                    _PRESIGN,
                    return_value="https://fresh-url.com/export.zip",
                ) as mock_gen,
            ):
                resp = await client.get("/api/v1/admin/export/progress/task-456")
                assert resp.status_code == 200
                data = resp.json()
                # Should use the freshly generated URL, not the cached one
                assert data["download_url"] == "https://fresh-url.com/export.zip"
                assert data["status"] == "SUCCESS"
                # Verify it was called with the storage_key from progress hash
                mock_gen.assert_called_once()
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_progress_success_fallback_to_celery_result(self, client):
        """B6: Falls back to Celery result URL when storage_key not in progress hash."""
        try:
            _override_auth("SUPER_ADMIN")
            mock_redis = AsyncMock()
            # No storage_key in progress hash (old export before this fix)
            mock_redis.hgetall = AsyncMock(
                return_value={"phase": "done", "current": "1", "total": "1", "zip_size": "12345"}
            )

            mock_result = MagicMock()
            mock_result.state = "SUCCESS"
            mock_result.result = {"download_url": "https://cached-url.com/export.zip"}

            with (
                patch(_REDIS, return_value=mock_redis),
                patch("celery.result.AsyncResult", return_value=mock_result),
            ):
                resp = await client.get("/api/v1/admin/export/progress/task-old")
                assert resp.status_code == 200
                data = resp.json()
                assert data["download_url"] == "https://cached-url.com/export.zip"
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_progress_failure_sanitizes_detail_field(self, client):
        """S2: The detail field is also sanitized when phase is 'failed'."""
        try:
            _override_auth("SUPER_ADMIN")
            mock_redis = AsyncMock()
            mock_redis.hgetall = AsyncMock(
                return_value={
                    "phase": "failed",
                    "detail": 'asyncpg.ConnectionRefusedError: could not connect',
                }
            )

            mock_result = MagicMock()
            mock_result.state = "FAILURE"
            mock_result.result = Exception("Storage unavailable")

            with (
                patch(_REDIS, return_value=mock_redis),
                patch("celery.result.AsyncResult", return_value=mock_result),
            ):
                resp = await client.get("/api/v1/admin/export/progress/task-detail")
                assert resp.status_code == 200
                data = resp.json()
                # detail should be sanitized too, not just error
                assert "asyncpg" not in (data["detail"] or "")
                assert "internal error" in data["detail"].lower()
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_progress_failure_sanitizes_internal_error(self, client):
        """S2: Internal details in error messages are replaced with safe message."""
        try:
            _override_auth("SUPER_ADMIN")
            mock_redis = AsyncMock()
            mock_redis.hgetall = AsyncMock(
                return_value={"phase": "failed", "detail": "Connection failed"}
            )

            mock_result = MagicMock()
            mock_result.state = "FAILURE"
            # Error with internal path info
            mock_result.result = Exception(
                'File "/app/tasks/site_export.py", line 100, asyncpg.ConnectionError'
            )

            with (
                patch(_REDIS, return_value=mock_redis),
                patch("celery.result.AsyncResult", return_value=mock_result),
            ):
                resp = await client.get("/api/v1/admin/export/progress/task-789")
                assert resp.status_code == 200
                data = resp.json()
                assert data["status"] == "FAILURE"
                # Should NOT contain internal path
                assert "/app/tasks/" not in (data["error"] or "")
                assert "internal error" in data["error"].lower()
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_progress_failure_safe_error_passthrough(self, client):
        """S2: Non-internal error messages are passed through (truncated)."""
        try:
            _override_auth("SUPER_ADMIN")
            mock_redis = AsyncMock()
            mock_redis.hgetall = AsyncMock(
                return_value={"phase": "failed"}
            )

            mock_result = MagicMock()
            mock_result.state = "FAILURE"
            mock_result.result = Exception("Storage unavailable")

            with (
                patch(_REDIS, return_value=mock_redis),
                patch("celery.result.AsyncResult", return_value=mock_result),
            ):
                resp = await client.get("/api/v1/admin/export/progress/task-safe")
                assert resp.status_code == 200
                data = resp.json()
                assert data["error"] == "Storage unavailable"
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_progress_admin_forbidden(self, client):
        """GET progress → 403 for non-SUPER_ADMIN."""
        try:
            _override_auth("ADMIN")
            resp = await client.get("/api/v1/admin/export/progress/task-123")
            assert resp.status_code == 403
        finally:
            _clear_overrides()


# ── GET /admin/export/history ─────────────────────────────────────────────


class TestExportHistory:
    @pytest.mark.anyio
    async def test_history_returns_list(self, client):
        """GET /admin/export/history → list of past exports."""
        try:
            _override_auth("SUPER_ADMIN")
            mock_redis = AsyncMock()
            entries = [
                json.dumps(
                    {
                        "task_id": "t1",
                        "status": "SUCCESS",
                        "created_at": "2026-03-25T14:00:00Z",
                        "created_by": str(uuid.uuid4()),
                        "options": {"include_database": True, "include_files": True},
                        "file_size": 5000000,
                        "storage_key": "exports/site-backup/t1/abc.zip",
                    }
                ),
            ]
            mock_redis.zrevrange = AsyncMock(return_value=entries)

            mock_client = MagicMock()
            mock_client.head_object = MagicMock(return_value={})

            with (
                patch(_REDIS, return_value=mock_redis),
                patch(_STORAGE, return_value=mock_client),
                patch(
                    _PRESIGN,
                    return_value="https://example.com/download.zip",
                ),
            ):
                resp = await client.get("/api/v1/admin/export/history")
                assert resp.status_code == 200
                data = resp.json()
                assert len(data["exports"]) == 1
                assert data["exports"][0]["task_id"] == "t1"
                assert data["exports"][0]["download_url"] == "https://example.com/download.zip"
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_history_empty(self, client):
        """GET /admin/export/history → empty list when no exports."""
        try:
            _override_auth("SUPER_ADMIN")
            mock_redis = AsyncMock()
            mock_redis.zrevrange = AsyncMock(return_value=[])

            with patch(_REDIS, return_value=mock_redis):
                resp = await client.get("/api/v1/admin/export/history")
                assert resp.status_code == 200
                data = resp.json()
                assert data["exports"] == []
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_history_expired_file(self, client):
        """GET history → download_url is None when S3 file no longer exists."""
        try:
            _override_auth("SUPER_ADMIN")
            mock_redis = AsyncMock()
            entries = [
                json.dumps(
                    {
                        "task_id": "t-old",
                        "status": "SUCCESS",
                        "created_at": "2026-03-18T10:00:00Z",
                        "created_by": str(uuid.uuid4()),
                        "options": {"include_database": True, "include_files": False},
                        "file_size": 1000,
                        "storage_key": "exports/site-backup/t-old/xyz.zip",
                    }
                ),
            ]
            mock_redis.zrevrange = AsyncMock(return_value=entries)

            mock_client = MagicMock()
            from botocore.exceptions import ClientError

            mock_client.head_object = MagicMock(
                side_effect=ClientError({"Error": {"Code": "404"}}, "HeadObject")
            )

            with (
                patch(_REDIS, return_value=mock_redis),
                patch(_STORAGE, return_value=mock_client),
            ):
                resp = await client.get("/api/v1/admin/export/history")
                assert resp.status_code == 200
                data = resp.json()
                assert len(data["exports"]) == 1
                assert data["exports"][0]["download_url"] is None
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_history_admin_forbidden(self, client):
        """GET history → 403 for non-SUPER_ADMIN."""
        try:
            _override_auth("ADMIN")
            resp = await client.get("/api/v1/admin/export/history")
            assert resp.status_code == 403
        finally:
            _clear_overrides()


# ── DELETE /admin/export/{task_id} ────────────────────────────────────────


class TestDeleteExport:
    @pytest.mark.anyio
    async def test_delete_export_success(self, client):
        """DELETE /admin/export/{task_id} → 200 deletes file and history entry."""
        try:
            _override_auth("SUPER_ADMIN")
            entry = json.dumps(
                {
                    "task_id": "t-del",
                    "status": "SUCCESS",
                    "created_at": "2026-03-25T12:00:00Z",
                    "created_by": str(uuid.uuid4()),
                    "options": {"include_database": True, "include_files": True},
                    "file_size": 5000,
                    "storage_key": "exports/site-backup/t-del/abc.zip",
                }
            )
            mock_redis = AsyncMock()
            mock_redis.zrange = AsyncMock(return_value=[entry])
            mock_redis.zrem = AsyncMock(return_value=1)
            mock_redis.delete = AsyncMock()

            mock_client = MagicMock()
            mock_client.delete_object = MagicMock()

            with (
                patch(_REDIS, return_value=mock_redis),
                patch(_STORAGE, return_value=mock_client),
                patch(_EMIT, new_callable=AsyncMock),
            ):
                resp = await client.delete("/api/v1/admin/export/t-del")
                assert resp.status_code == 200
                mock_client.delete_object.assert_called_once()
                mock_redis.zrem.assert_called_once()
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_delete_export_not_found(self, client):
        """DELETE /admin/export/{task_id} → 404 when entry doesn't exist."""
        try:
            _override_auth("SUPER_ADMIN")
            mock_redis = AsyncMock()
            mock_redis.zrange = AsyncMock(return_value=[])

            with patch(_REDIS, return_value=mock_redis):
                resp = await client.delete("/api/v1/admin/export/nonexistent")
                assert resp.status_code == 404
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_delete_export_admin_forbidden(self, client):
        """DELETE /admin/export/{task_id} → 403 for ADMIN."""
        try:
            _override_auth("ADMIN")
            resp = await client.delete("/api/v1/admin/export/t-del")
            assert resp.status_code == 403
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_delete_task_id_path_validation(self, client):
        """S3: DELETE /admin/export/{task_id} validates task_id length."""
        try:
            _override_auth("SUPER_ADMIN")
            # task_id exceeding max_length=64 should get 422
            long_id = "x" * 65
            resp = await client.delete(f"/api/v1/admin/export/{long_id}")
            assert resp.status_code == 422
        finally:
            _clear_overrides()


# ── Task logic unit tests ─────────────────────────────────────────────────


class TestExportTaskLogic:
    def test_json_serial_uuid(self):
        """_json_serial handles UUID correctly."""
        from app.tasks.site_export import _json_serial

        uid = uuid.uuid4()
        assert _json_serial(uid) == str(uid)

    def test_json_serial_datetime(self):
        """_json_serial handles datetime correctly."""
        from datetime import datetime, timezone

        from app.tasks.site_export import _json_serial

        dt = datetime(2026, 3, 25, 14, 30, 0, tzinfo=timezone.utc)
        assert _json_serial(dt) == "2026-03-25T14:30:00+00:00"

    def test_json_serial_bytes(self):
        """_json_serial handles bytes via base64."""
        from app.tasks.site_export import _json_serial

        result = _json_serial(b"\x00\x01\x02")
        assert result == "AAEC"

    def test_json_serial_unknown_type_raises(self):
        """_json_serial raises TypeError for unsupported types."""
        from app.tasks.site_export import _json_serial

        with pytest.raises(TypeError):
            _json_serial(set())

    def test_export_tables_list_not_empty(self):
        """_EXPORT_TABLES should have all expected tables."""
        from app.tasks.site_export import _EXPORT_TABLES

        assert len(_EXPORT_TABLES) >= 30
        assert "users" in _EXPORT_TABLES
        assert "posts" in _EXPORT_TABLES
        assert "dm_messages" in _EXPORT_TABLES
        assert "audit_logs" in _EXPORT_TABLES

    def test_export_tables_no_duplicates(self):
        """_EXPORT_TABLES should not have duplicates."""
        from app.tasks.site_export import _EXPORT_TABLES

        assert len(_EXPORT_TABLES) == len(set(_EXPORT_TABLES))

    def test_lock_key_constant(self):
        """Lock key should be a known constant."""
        from app.tasks.site_export import LOCK_KEY

        assert LOCK_KEY == "export:site:lock"

    def test_progress_key_prefix(self):
        """Progress key prefix should be set."""
        from app.tasks.site_export import PROGRESS_KEY_PREFIX

        assert PROGRESS_KEY_PREFIX == "export:progress:"

    def test_excluded_columns_contains_password_hash(self):
        """S1: password_hash must be excluded from users table export."""
        from app.tasks.site_export import _EXCLUDED_COLUMNS

        assert "users" in _EXCLUDED_COLUMNS
        assert "password_hash" in _EXCLUDED_COLUMNS["users"]

    def test_lua_acquire_lock_accepts_pending(self):
        """B2: _LUA_ACQUIRE_LOCK script should accept 'pending' value."""
        from app.tasks.site_export import _LUA_ACQUIRE_LOCK

        assert "pending" in _LUA_ACQUIRE_LOCK

    def test_progress_ttl_constant(self):
        """B8: _PROGRESS_TTL should be positive."""
        from app.tasks.site_export import _PROGRESS_TTL

        assert _PROGRESS_TTL == 86400


# ── Error sanitisation tests ─────────────────────────────────────────────


class TestErrorSanitisation:
    def test_sanitize_internal_path(self):
        """S2: Error with Python file paths is sanitized."""
        from app.api.v1.endpoints.export import _sanitize_error

        result = _sanitize_error('File "/app/core/database.py", line 42, in get_pool')
        assert "database.py" not in result
        assert "internal error" in result.lower()

    def test_sanitize_asyncpg_error(self):
        """S2: asyncpg connection errors are sanitized."""
        from app.api.v1.endpoints.export import _sanitize_error

        result = _sanitize_error("asyncpg.ConnectionRefusedError: could not connect to server")
        assert "asyncpg" not in result

    def test_sanitize_postgresql_url(self):
        """S2: PostgreSQL connection URLs are sanitized."""
        from app.api.v1.endpoints.export import _sanitize_error

        result = _sanitize_error("postgresql://user:password@host:5432/db")
        assert "postgresql://" not in result

    def test_sanitize_redis_url(self):
        """S2: Redis connection URLs are sanitized."""
        from app.api.v1.endpoints.export import _sanitize_error

        result = _sanitize_error("redis://localhost:6379/0")
        assert "redis://" not in result

    def test_sanitize_traceback(self):
        """S2: Traceback strings are sanitized."""
        from app.api.v1.endpoints.export import _sanitize_error

        result = _sanitize_error("Traceback (most recent call last):")
        assert "Traceback" not in result

    def test_sanitize_safe_message_passthrough(self):
        """S2: Safe error messages pass through unchanged."""
        from app.api.v1.endpoints.export import _sanitize_error

        result = _sanitize_error("Storage unavailable")
        assert result == "Storage unavailable"

    def test_sanitize_none(self):
        """S2: None input returns None."""
        from app.api.v1.endpoints.export import _sanitize_error

        assert _sanitize_error(None) is None

    def test_sanitize_empty_string(self):
        """S2: Empty string returns empty string."""
        from app.api.v1.endpoints.export import _sanitize_error

        assert _sanitize_error("") == ""

    def test_sanitize_truncates_long_messages(self):
        """S2: Long safe messages are truncated to 200 chars."""
        from app.api.v1.endpoints.export import _sanitize_error

        long_msg = "A" * 500
        result = _sanitize_error(long_msg)
        assert len(result) == 200


# ── Constants tests ───────────────────────────────────────────────────────


class TestExportConstants:
    def test_rate_limit_configured(self):
        from app.core.constants import RATE_LIMIT_SITE_EXPORT

        max_count, window = RATE_LIMIT_SITE_EXPORT
        assert max_count == 1
        assert window == 1800

    def test_max_zip_size(self):
        from app.core.constants import EXPORT_MAX_ZIP_BYTES

        assert EXPORT_MAX_ZIP_BYTES == 10 * 1024 * 1024 * 1024

    def test_presigned_ttl_short(self):
        from app.core.constants import EXPORT_PRESIGNED_TTL_SECONDS

        # Must be short for security (15 min)
        assert EXPORT_PRESIGNED_TTL_SECONDS <= 900

    def test_lock_ttl_exceeds_hard_limit(self):
        from app.core.constants import EXPORT_LOCK_TTL_SECONDS

        # Lock TTL must exceed Celery hard time limit (7200s)
        assert EXPORT_LOCK_TTL_SECONDS > 7200

    def test_cleanup_days_positive(self):
        from app.core.constants import EXPORT_CLEANUP_DAYS

        assert EXPORT_CLEANUP_DAYS > 0


# ── Schema tests ──────────────────────────────────────────────────────────


class TestExportSchemas:
    def test_site_export_request_defaults(self):
        from app.schemas.export import SiteExportRequest

        req = SiteExportRequest()
        assert req.include_database is True
        assert req.include_files is True

    def test_site_export_request_partial(self):
        from app.schemas.export import SiteExportRequest

        req = SiteExportRequest(include_database=True, include_files=False)
        assert req.include_database is True
        assert req.include_files is False

    def test_export_progress_response_defaults(self):
        from app.schemas.export import ExportProgressResponse

        resp = ExportProgressResponse(task_id="t1", status="PENDING")
        assert resp.current == 0
        assert resp.total == 0
        assert resp.download_url is None
        assert resp.error is None

    def test_export_history_item(self):
        from app.schemas.export import ExportHistoryItem

        item = ExportHistoryItem(
            task_id="t1",
            status="SUCCESS",
            created_at="2026-03-25T14:00:00Z",
            created_by="user-id",
            options={"include_database": True, "include_files": True},
            file_size=5000000,
            download_url="https://example.com/dl.zip",
        )
        assert item.file_size == 5000000

    def test_export_history_response(self):
        from app.schemas.export import ExportHistoryResponse

        resp = ExportHistoryResponse(exports=[])
        assert resp.exports == []


# ── Cleanup task tests ───────────────────────────────────────────────────


class TestCleanupSafety:
    @pytest.mark.anyio
    async def test_cleanup_skips_failed_s3_deletions(self):
        """B5: History entries are NOT removed when S3 delete fails."""
        from app.tasks.site_export import _async_cleanup_old_exports

        mock_redis = AsyncMock()
        success_entry = json.dumps({
            "task_id": "t-ok",
            "storage_key": "exports/site-backup/t-ok/a.zip",
        })
        fail_entry = json.dumps({
            "task_id": "t-fail",
            "storage_key": "exports/site-backup/t-fail/b.zip",
        })
        mock_redis.zrangebyscore = AsyncMock(return_value=[success_entry, fail_entry])
        mock_redis.zrem = AsyncMock()
        mock_redis.zcard = AsyncMock(return_value=2)

        mock_client = MagicMock()
        # First call succeeds, second fails
        mock_client.delete_object = MagicMock(
            side_effect=[None, Exception("S3 unavailable")]
        )

        with (
            patch("app.tasks.site_export._ensure_redis", new_callable=AsyncMock),
            patch("app.core.redis.get_redis", return_value=mock_redis),
            patch("app.tasks.site_export.get_storage", return_value=mock_client),
        ):
            deleted = await _async_cleanup_old_exports()

        assert deleted == 1
        # Only the successful entry should be removed
        mock_redis.zrem.assert_called_once_with("export:site:history", success_entry)

    @pytest.mark.anyio
    async def test_cleanup_removes_entries_without_storage_key(self):
        """B5: Failed export entries (no storage_key) are safely cleaned up."""
        from app.tasks.site_export import _async_cleanup_old_exports

        mock_redis = AsyncMock()
        no_file_entry = json.dumps({
            "task_id": "t-nofile",
            "storage_key": None,
            "status": "FAILURE",
        })
        mock_redis.zrangebyscore = AsyncMock(return_value=[no_file_entry])
        mock_redis.zrem = AsyncMock()

        mock_client = MagicMock()

        with (
            patch("app.tasks.site_export._ensure_redis", new_callable=AsyncMock),
            patch("app.core.redis.get_redis", return_value=mock_redis),
            patch("app.tasks.site_export.get_storage", return_value=mock_client),
        ):
            deleted = await _async_cleanup_old_exports()

        assert deleted == 1
        mock_redis.zrem.assert_called_once_with("export:site:history", no_file_entry)
        mock_client.delete_object.assert_not_called()
