"""Tests for infrastructure and data integrity fixes.

Covers:
- C2: VirusTotal Celery task uses sync storage calls (no bug)
- H1: SIG soft_delete removes sig_members
- H5: Request body size limit middleware
- H12: MINIO_PUBLIC_URL production validation
- M3: file_scan_repo insert_or_get race condition fix
- M4: category_repo find_all has LIMIT 500
- M8: Audit log pagination bounds
- M10: application_converter has no avatar fields (skip)
"""

import ast
import inspect
import os
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

_TEST_CSRF_TOKEN = "test-csrf-token"


# ===========================================================================
# C2: VirusTotal storage calls are sync (no bug — verify by inspection)
# ===========================================================================


class TestVirusTotalStorageCalls:
    """Verify that get_file_size and delete_file in storage.py are sync functions."""

    def test_get_file_size_is_sync(self):
        from app.core.storage import get_file_size

        assert not inspect.iscoroutinefunction(get_file_size), (
            "get_file_size should be a sync function (called from sync Celery task)"
        )

    def test_delete_file_is_sync(self):
        from app.core.storage import delete_file

        assert not inspect.iscoroutinefunction(delete_file), (
            "delete_file should be a sync function (called from sync Celery task)"
        )


# ===========================================================================
# H1: SIG soft_delete removes sig_members
# ===========================================================================


class TestSigSoftDeleteCleansUpMembers:
    """soft_delete() must DELETE sig_members inside the same transaction."""

    @pytest.mark.anyio
    async def test_soft_delete_removes_sig_members(self, mock_pool, mock_conn):
        """After soft_delete, sig_members rows for that SIG should be deleted."""
        from app.repositories import sig_repo

        sig_id = uuid.uuid4()
        mock_conn.execute = AsyncMock(return_value="UPDATE 1")

        with patch("app.repositories.sig_repo.get_pool", return_value=mock_pool):
            result = await sig_repo.soft_delete(sig_id)

        assert result is True

        # Collect all SQL executed
        calls = mock_conn.execute.call_args_list
        sql_statements = [str(c[0][0]) for c in calls]

        # Verify sig_members cleanup was called
        member_delete_found = any(
            "DELETE FROM sig_members" in sql and "sig_id" in sql
            for sql in sql_statements
        )
        assert member_delete_found, (
            f"Expected DELETE FROM sig_members in transaction. Got: {sql_statements}"
        )

        # Verify it was called with the correct sig_id
        member_delete_call = [
            c for c in calls if "DELETE FROM sig_members" in str(c[0][0])
        ]
        assert len(member_delete_call) == 1
        assert member_delete_call[0][0][1] == sig_id

        # Verify transaction was used
        mock_conn.transaction.assert_called_once()

    @pytest.mark.anyio
    async def test_soft_delete_not_found_skips_cleanup(self, mock_pool, mock_conn):
        """If the SIG doesn't exist (UPDATE 0), no member cleanup occurs."""
        from app.repositories import sig_repo

        sig_id = uuid.uuid4()
        mock_conn.execute = AsyncMock(return_value="UPDATE 0")

        with patch("app.repositories.sig_repo.get_pool", return_value=mock_pool):
            result = await sig_repo.soft_delete(sig_id)

        assert result is False
        # Only the first UPDATE should have been called (returns UPDATE 0 = early exit)
        assert mock_conn.execute.await_count == 1

    @pytest.mark.anyio
    async def test_soft_delete_order_of_operations(self, mock_pool, mock_conn):
        """Operations must happen in order: sigs, posts, forms, sig_members."""
        from app.repositories import sig_repo

        sig_id = uuid.uuid4()
        mock_conn.execute = AsyncMock(return_value="UPDATE 1")

        with patch("app.repositories.sig_repo.get_pool", return_value=mock_pool):
            await sig_repo.soft_delete(sig_id)

        calls = mock_conn.execute.call_args_list
        sql_statements = [str(c[0][0]) for c in calls]

        assert len(sql_statements) == 4
        assert "UPDATE sigs" in sql_statements[0]
        assert "UPDATE posts" in sql_statements[1]
        assert "UPDATE forms" in sql_statements[2]
        assert "DELETE FROM sig_members" in sql_statements[3]


# ===========================================================================
# H5: Request body size limit middleware
# ===========================================================================


class TestRequestBodySizeLimit:
    """Middleware should reject requests with Content-Length > 10MB."""

    @pytest.mark.anyio
    async def test_oversized_request_rejected(self, client: AsyncClient):
        """A request claiming >10MB Content-Length should get 413."""
        resp = await client.post(
            "/api/v1/health",
            headers={"content-length": str(11 * 1024 * 1024)},
            content=b"x",
        )
        assert resp.status_code == 413
        assert resp.json()["detail"] == "Request body too large"

    @pytest.mark.anyio
    async def test_normal_request_allowed(self, client: AsyncClient):
        """A request with normal Content-Length should pass through."""
        # Health endpoint should respond (not blocked by size limit)
        mock_conn = AsyncMock()
        mock_conn.fetchval = AsyncMock(return_value=1)
        cm = AsyncMock()
        cm.__aenter__ = AsyncMock(return_value=mock_conn)
        cm.__aexit__ = AsyncMock(return_value=False)
        mock_pool = MagicMock()
        mock_pool.acquire.return_value = cm

        mock_redis = AsyncMock()
        mock_redis.ping = AsyncMock(return_value=True)

        mock_storage = MagicMock()
        mock_storage.head_bucket = MagicMock(return_value={})

        with (
            patch("app.api.v1.endpoints.health.get_pool", return_value=mock_pool),
            patch("app.api.v1.endpoints.health.get_redis", return_value=mock_redis),
            patch("app.core.storage.get_storage", return_value=mock_storage),
        ):
            resp = await client.get("/api/v1/health")

        assert resp.status_code == 200

    def test_max_body_size_constant(self):
        """MAX_REQUEST_BODY_SIZE should be 10MB."""
        from app.main import MAX_REQUEST_BODY_SIZE

        assert MAX_REQUEST_BODY_SIZE == 10 * 1024 * 1024

    @pytest.mark.anyio
    async def test_exactly_10mb_allowed(self, client: AsyncClient):
        """A request with exactly 10MB Content-Length should pass through."""
        # 10MB exactly should NOT be rejected (only > 10MB is rejected)
        # We use a nonexistent endpoint; the point is it should NOT get 413
        resp = await client.post(
            "/api/v1/nonexistent",
            headers={"content-length": str(10 * 1024 * 1024)},
            content=b"x",
        )
        assert resp.status_code != 413


# ===========================================================================
# H12: MINIO_PUBLIC_URL production validation
# ===========================================================================


class TestMinioPublicUrlValidation:
    """In production mode, empty MINIO_PUBLIC_URL should abort startup."""

    def test_production_check_includes_minio_public_url(self):
        """The lifespan function should check MINIO_PUBLIC_URL in production."""
        source_path = os.path.join(
            os.path.dirname(__file__), "..", "app", "main.py"
        )
        with open(source_path, encoding="utf-8") as f:
            source = f.read()

        assert "MINIO_PUBLIC_URL" in source
        assert "MINIO_PUBLIC_URL must be set in production" in source

    def test_production_check_exits_on_empty_minio_url(self):
        """Verify the production security check aborts when MINIO_PUBLIC_URL is empty."""
        source_path = os.path.join(
            os.path.dirname(__file__), "..", "app", "main.py"
        )
        with open(source_path, encoding="utf-8") as f:
            source = f.read()

        tree = ast.parse(source)

        # Find the check: if not settings.MINIO_PUBLIC_URL
        found_check = False
        for node in ast.walk(tree):
            if isinstance(node, ast.If):
                # Look for `not settings.MINIO_PUBLIC_URL`
                test = node.test
                if (
                    isinstance(test, ast.UnaryOp)
                    and isinstance(test.op, ast.Not)
                    and isinstance(test.operand, ast.Attribute)
                    and getattr(test.operand, "attr", "") == "MINIO_PUBLIC_URL"
                ):
                    found_check = True
                    break

        assert found_check, "Production check for MINIO_PUBLIC_URL not found in main.py"


# ===========================================================================
# M3: file_scan_repo insert uses atomic UPSERT
# ===========================================================================


class TestFileScanRepoUpsert:
    """insert() should use ON CONFLICT DO UPDATE to always return a row."""

    @pytest.mark.anyio
    async def test_insert_new_record(self, mock_pool, mock_conn):
        """Inserting a new file_key should return the record."""
        from app.repositories import file_scan_repo

        now = datetime.now(timezone.utc)
        mock_conn.fetchrow = AsyncMock(
            return_value={
                "id": uuid.uuid4(),
                "file_key": "uploads/test.txt",
                "status": "pending",
                "scan_id": None,
                "positives": None,
                "total": None,
                "created_at": now,
                "updated_at": now,
            }
        )

        with patch("app.repositories.file_scan_repo.get_pool", return_value=mock_pool):
            result = await file_scan_repo.insert("uploads/test.txt")

        assert result is not None
        assert result["file_key"] == "uploads/test.txt"
        assert result["status"] == "pending"

    @pytest.mark.anyio
    async def test_insert_conflict_returns_existing(self, mock_pool, mock_conn):
        """ON CONFLICT should still return the row (via DO UPDATE RETURNING *)."""
        from app.repositories import file_scan_repo

        now = datetime.now(timezone.utc)
        existing_id = uuid.uuid4()
        mock_conn.fetchrow = AsyncMock(
            return_value={
                "id": existing_id,
                "file_key": "uploads/test.txt",
                "status": "clean",
                "scan_id": "abc",
                "positives": 0,
                "total": 60,
                "created_at": now,
                "updated_at": now,
            }
        )

        with patch("app.repositories.file_scan_repo.get_pool", return_value=mock_pool):
            result = await file_scan_repo.insert("uploads/test.txt")

        assert result is not None
        assert result["id"] == existing_id
        # Single query, no race window
        mock_conn.fetchrow.assert_awaited_once()

    @pytest.mark.anyio
    async def test_insert_returns_none_not_empty_dict(self, mock_pool, mock_conn):
        """If somehow no row is returned, should return None (not {})."""
        from app.repositories import file_scan_repo

        mock_conn.fetchrow = AsyncMock(return_value=None)

        with patch("app.repositories.file_scan_repo.get_pool", return_value=mock_pool):
            result = await file_scan_repo.insert("uploads/test.txt")

        assert result is None

    def test_insert_uses_do_update_not_do_nothing(self):
        """The SQL should use ON CONFLICT DO UPDATE, not DO NOTHING."""
        import app.repositories.file_scan_repo as module

        source = inspect.getsource(module.insert)
        assert "DO UPDATE" in source
        assert "DO NOTHING" not in source


# ===========================================================================
# M4: category_repo find_all has LIMIT
# ===========================================================================


class TestCategoryRepoFindAllLimit:
    """find_all() should include a LIMIT clause."""

    @pytest.mark.anyio
    async def test_find_all_has_limit_in_query(self, mock_pool, mock_conn):
        """The SQL executed should include LIMIT 500."""
        from app.repositories import category_repo

        mock_conn.fetch = AsyncMock(return_value=[])

        with patch("app.repositories.category_repo.get_pool", return_value=mock_pool):
            await category_repo.find_all()

        # Check the SQL passed to fetch
        call_args = mock_conn.fetch.call_args
        sql = call_args[0][0]
        assert "LIMIT 500" in sql

    def test_find_all_source_contains_limit(self):
        """Static check: find_all source code contains LIMIT."""
        import app.repositories.category_repo as module

        source = inspect.getsource(module.find_all)
        assert "LIMIT" in source, "find_all() must include a LIMIT clause"


# ===========================================================================
# M8: Audit log pagination bounds
# ===========================================================================


class TestAuditLogPaginationBounds:
    """Audit log endpoint should reject oversized page/page_size values."""

    @pytest.mark.anyio
    async def test_page_exceeds_max_rejected(self, client: AsyncClient):
        """page > 1000 should be rejected by FastAPI validation."""
        from app.core.deps import get_current_user
        from app.main import app

        payload = {
            "sub": str(uuid.uuid4()),
            "role": "SUPER_ADMIN",
            "jti": str(uuid.uuid4()),
        }
        app.dependency_overrides[get_current_user] = lambda: payload

        try:
            resp = await client.get(
                "/api/v1/users/admin/audit-logs",
                params={"page": 1001},
            )
            assert resp.status_code == 422
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.anyio
    async def test_page_size_exceeds_max_rejected(self, client: AsyncClient):
        """page_size > 50 should be rejected by FastAPI validation."""
        from app.core.deps import get_current_user
        from app.main import app

        payload = {
            "sub": str(uuid.uuid4()),
            "role": "SUPER_ADMIN",
            "jti": str(uuid.uuid4()),
        }
        app.dependency_overrides[get_current_user] = lambda: payload

        try:
            resp = await client.get(
                "/api/v1/users/admin/audit-logs",
                params={"page_size": 51},
            )
            assert resp.status_code == 422
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.anyio
    async def test_valid_pagination_accepted(self, client: AsyncClient):
        """Valid page=1, page_size=20 should not be rejected by validation."""
        from app.core.deps import get_current_user
        from app.main import app

        payload = {
            "sub": str(uuid.uuid4()),
            "role": "SUPER_ADMIN",
            "jti": str(uuid.uuid4()),
        }
        app.dependency_overrides[get_current_user] = lambda: payload

        try:
            with patch(
                "app.api.v1.endpoints.users.list_audit_logs",
                new_callable=AsyncMock,
                return_value=([], 0),
            ):
                resp = await client.get(
                    "/api/v1/users/admin/audit-logs",
                    params={"page": 1, "page_size": 20},
                )
            # Should not be 422 (validation error)
            assert resp.status_code != 422
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.anyio
    async def test_page_1000_accepted(self, client: AsyncClient):
        """page=1000 (the max) should be accepted."""
        from app.core.deps import get_current_user
        from app.main import app

        payload = {
            "sub": str(uuid.uuid4()),
            "role": "SUPER_ADMIN",
            "jti": str(uuid.uuid4()),
        }
        app.dependency_overrides[get_current_user] = lambda: payload

        try:
            with patch(
                "app.api.v1.endpoints.users.list_audit_logs",
                new_callable=AsyncMock,
                return_value=([], 0),
            ):
                resp = await client.get(
                    "/api/v1/users/admin/audit-logs",
                    params={"page": 1000, "page_size": 50},
                )
            assert resp.status_code != 422
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.anyio
    async def test_page_size_default_is_20(self):
        """Default page_size should now be 20 (not 50)."""
        source_path = os.path.join(
            os.path.dirname(__file__), "..", "app", "api", "v1", "endpoints", "users.py"
        )
        with open(source_path, encoding="utf-8") as f:
            source = f.read()

        # Find the get_audit_logs function and check its default page_size
        # Look for: page_size: int = Query(20, ge=1, le=50)
        assert "Query(20, ge=1, le=50)" in source, (
            "Audit log page_size should default to 20 with max 50"
        )
        assert "Query(1, ge=1, le=1000)" in source, (
            "Audit log page should default to 1 with max 1000"
        )


# ===========================================================================
# M10: application_converter — no avatar fields (verification only)
# ===========================================================================


class TestApplicationConverterNoAvatar:
    """application_converter does not have avatar fields, so no fix needed."""

    def test_no_avatar_url_in_application_converter(self):
        """row_to_application should NOT contain avatar_url field."""
        from app.converters.application_converter import row_to_application

        source = inspect.getsource(row_to_application)
        assert "avatar_url" not in source, (
            "application_converter should not reference avatar_url "
            "(the applications query does not join avatar data)"
        )
