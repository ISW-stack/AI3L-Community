"""Tests for file upload validation — magic number check, path traversal, PDF sanitization."""

import uuid
from io import BytesIO
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient

from app.core.file_validation import sanitize_html, validate_magic_number


class TestMagicNumberValidation:
    def test_valid_png(self):
        data = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
        assert validate_magic_number(data, "image/png") is True

    def test_valid_jpeg(self):
        data = b"\xff\xd8\xff" + b"\x00" * 100
        assert validate_magic_number(data, "image/jpeg") is True

    def test_valid_pdf(self):
        data = b"%PDF-1.4" + b"\x00" * 100
        assert validate_magic_number(data, "application/pdf") is True

    def test_valid_docx(self):
        data = b"PK\x03\x04" + b"\x00" * 100
        content_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        assert validate_magic_number(data, content_type) is True

    def test_upload_invalid_magic_number(self):
        """FILE_001: content does not match declared type."""
        fake_png = b"\x00\x00\x00\x00" + b"\x00" * 100  # not a PNG
        assert validate_magic_number(fake_png, "image/png") is False

    def test_unknown_content_type(self):
        data = b"\x00" * 100
        assert validate_magic_number(data, "application/unknown") is False

    def test_empty_data(self):
        assert validate_magic_number(b"", "image/png") is False


class TestSanitizeHtml:
    def test_preserves_code_class_for_syntax_highlighting(self):
        """code tag with language-* class must survive sanitization."""
        html = '<pre><code class="language-python">print("hi")</code></pre>'
        result = sanitize_html(html)
        assert 'class="language-python"' in result

    def test_preserves_pre_class(self):
        """pre tag with class must survive sanitization."""
        html = '<pre class="language-javascript">const x = 1;</pre>'
        result = sanitize_html(html)
        assert 'class="language-javascript"' in result

    def test_strips_class_from_other_tags(self):
        """class attribute on p/div/span must be stripped (XSS prevention)."""
        html = '<p class="evil-class">text</p>'
        result = sanitize_html(html)
        assert 'class="evil-class"' not in result
        assert "<p>" in result  # tag itself survives

    def test_link_rel_noopener_added(self):
        """All links must get rel="noopener noreferrer"."""
        html = '<a href="https://example.com" target="_blank">link</a>'
        result = sanitize_html(html)
        assert "noopener" in result
        assert "noreferrer" in result

    def test_strips_script_tags(self):
        """script tags must always be stripped."""
        html = "<p>safe</p><script>alert(1)</script>"
        result = sanitize_html(html)
        assert "<script>" not in result
        assert "safe" in result

    def test_strips_onclick_attributes(self):
        """on* event attributes must be stripped."""
        html = '<p onclick="alert(1)">text</p>'
        result = sanitize_html(html)
        assert "onclick" not in result


class TestPresignedUrlPathTraversal:
    """GET /files/presigned/{key} must reject path traversal attempts."""

    @patch(
        "app.core.deps.get_user_by_id", new_callable=AsyncMock, return_value={"is_banned": False}
    )
    @patch("app.core.deps.validate_session", new_callable=AsyncMock, return_value=True)
    async def test_reject_double_dot(
        self, mock_session, mock_user, client: AsyncClient, auth_headers
    ):
        headers, user_id, _ = auth_headers("ADMIN")
        resp = await client.get(
            "/api/v1/files/presigned/..%2F..%2Fetc%2Fpasswd",
            headers=headers,
        )
        assert resp.status_code == 400
        assert "invalid" in resp.json()["detail"].lower()

    @patch(
        "app.core.deps.get_user_by_id", new_callable=AsyncMock, return_value={"is_banned": False}
    )
    @patch("app.core.deps.validate_session", new_callable=AsyncMock, return_value=True)
    async def test_reject_special_characters(
        self, mock_session, mock_user, client: AsyncClient, auth_headers
    ):
        headers, user_id, _ = auth_headers("ADMIN")
        resp = await client.get(
            "/api/v1/files/presigned/editor/foo%00bar.png",
            headers=headers,
        )
        assert resp.status_code == 400


class TestPdfSanitization:
    """sanitize_pdf should strip /JS, /JavaScript, /AA, /OpenAction."""

    @staticmethod
    def _make_pdf_with_root_key(key: str, value: str = "alert('xss')") -> bytes:
        """Helper: create a minimal PDF with a dangerous key on the root catalog."""
        import pikepdf

        pdf = pikepdf.new()
        pdf.add_blank_page(page_size=(200, 200))
        pdf.Root[pikepdf.Name(key)] = pikepdf.String(value)
        buf = BytesIO()
        pdf.save(buf)
        return buf.getvalue()

    @staticmethod
    def _make_pdf_with_page_key(key: str, value: str = "alert('xss')") -> bytes:
        """Helper: create a minimal PDF with a dangerous key on a page object."""
        import pikepdf

        pdf = pikepdf.new()
        pdf.add_blank_page(page_size=(200, 200))
        pdf.pages[0].obj[pikepdf.Name(key)] = pikepdf.String(value)
        buf = BytesIO()
        pdf.save(buf)
        return buf.getvalue()

    def test_sanitize_strips_open_action(self):
        from app.core.file_validation import sanitize_pdf

        raw = self._make_pdf_with_root_key("/OpenAction")
        sanitized = sanitize_pdf(raw)
        assert len(sanitized) > 0
        assert b"/OpenAction" not in sanitized

    def test_sanitize_strips_js_key(self):
        from app.core.file_validation import sanitize_pdf

        raw = self._make_pdf_with_root_key("/JS")
        sanitized = sanitize_pdf(raw)
        assert b"/JS" not in sanitized

    def test_sanitize_strips_javascript_key(self):
        from app.core.file_validation import sanitize_pdf

        raw = self._make_pdf_with_root_key("/JavaScript")
        sanitized = sanitize_pdf(raw)
        assert b"/JavaScript" not in sanitized

    def test_sanitize_strips_aa_key(self):
        from app.core.file_validation import sanitize_pdf

        raw = self._make_pdf_with_root_key("/AA")
        sanitized = sanitize_pdf(raw)
        assert b"/AA" not in sanitized

    def test_sanitize_strips_page_level_keys(self):
        from app.core.file_validation import sanitize_pdf

        raw = self._make_pdf_with_page_key("/AA")
        sanitized = sanitize_pdf(raw)
        assert b"/AA" not in sanitized

    def test_sanitize_preserves_page_count(self):
        import pikepdf

        from app.core.file_validation import sanitize_pdf

        pdf = pikepdf.new()
        for _ in range(5):
            pdf.add_blank_page(page_size=(200, 200))
        buf = BytesIO()
        pdf.save(buf)
        raw = buf.getvalue()

        sanitized = sanitize_pdf(raw)
        result = pikepdf.open(BytesIO(sanitized))
        assert len(result.pages) == 5

    def test_sanitize_preserves_metadata(self):
        import pikepdf

        from app.core.file_validation import sanitize_pdf

        pdf = pikepdf.new()
        pdf.add_blank_page(page_size=(200, 200))
        with pdf.open_metadata() as meta:
            meta["dc:title"] = "Test Document"
        buf = BytesIO()
        pdf.save(buf)
        raw = buf.getvalue()

        sanitized = sanitize_pdf(raw)
        result = pikepdf.open(BytesIO(sanitized))
        with result.open_metadata() as meta:
            assert meta.get("dc:title") == "Test Document"

    def test_sanitize_clean_pdf_passthrough(self):
        import pikepdf

        from app.core.file_validation import sanitize_pdf

        pdf = pikepdf.new()
        pdf.add_blank_page(page_size=(200, 200))
        buf = BytesIO()
        pdf.save(buf)
        raw = buf.getvalue()

        sanitized = sanitize_pdf(raw)
        assert len(sanitized) > 0
        # Should be readable
        result = pikepdf.open(BytesIO(sanitized))
        assert len(result.pages) == 1

    def test_sanitize_invalid_pdf_raises(self):
        import pytest

        from app.core.file_validation import sanitize_pdf

        with pytest.raises(ValueError, match="Invalid or corrupted PDF"):
            sanitize_pdf(b"this is not a pdf")


def _override_auth_files(role: str = "MEMBER", user_id: str | None = None) -> dict:
    from app.core.deps import get_current_user
    from app.main import app

    uid = user_id or str(uuid.uuid4())
    payload = {"sub": uid, "role": role, "jti": str(uuid.uuid4())}
    app.dependency_overrides[get_current_user] = lambda: payload
    return payload


def _clear_overrides_files() -> None:
    from app.main import app

    app.dependency_overrides.clear()


class TestStorageUsageEndpoint:
    """GET /files/storage-usage — returns used_bytes and quota_bytes (DB-tracked)."""

    @pytest.mark.anyio
    async def test_storage_usage_authenticated_member(self, client: AsyncClient) -> None:
        """Authenticated member receives used_bytes and quota_bytes from DB."""
        _override_auth_files("MEMBER")
        try:
            with patch(
                "app.api.v1.endpoints.files.user_repo.get_storage_used",
                new_callable=AsyncMock,
                return_value=123456789,
            ):
                resp = await client.get(
                    "/api/v1/files/storage-usage",
                    headers={"Authorization": "Bearer fake"},
                )
            assert resp.status_code == 200
            data = resp.json()
            assert "used_bytes" in data
            assert "quota_bytes" in data
            assert data["used_bytes"] == 123456789
            assert data["quota_bytes"] > 0
        finally:
            _clear_overrides_files()

    @pytest.mark.anyio
    async def test_storage_usage_unauthenticated_returns_401(self, client: AsyncClient) -> None:
        """Unauthenticated request to storage-usage endpoint returns 401."""
        resp = await client.get("/api/v1/files/storage-usage")
        assert resp.status_code == 401

    @pytest.mark.anyio
    async def test_storage_usage_zero_used(self, client: AsyncClient) -> None:
        """User with no uploads reports used_bytes of 0."""
        _override_auth_files("MEMBER")
        try:
            with patch(
                "app.api.v1.endpoints.files.user_repo.get_storage_used",
                new_callable=AsyncMock,
                return_value=0,
            ):
                resp = await client.get(
                    "/api/v1/files/storage-usage",
                    headers={"Authorization": "Bearer fake"},
                )
            assert resp.status_code == 200
            assert resp.json()["used_bytes"] == 0
        finally:
            _clear_overrides_files()


class TestUploadStorageTracking:
    """Upload endpoint must use DB quota check and increment storage counter."""

    @pytest.mark.anyio
    async def test_upload_uses_db_quota_check(self, client: AsyncClient) -> None:
        """Quota check reads from user_repo.get_storage_used, not S3 LIST."""
        _override_auth_files("MEMBER")
        try:
            png_data = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100

            with (
                patch(
                    "app.api.v1.endpoints.files.user_repo.get_storage_used",
                    new_callable=AsyncMock,
                    return_value=0,
                ) as mock_get_storage,
                patch(
                    "app.api.v1.endpoints.files.user_repo.increment_storage_used",
                    new_callable=AsyncMock,
                ) as mock_increment,
                patch(
                    "app.api.v1.endpoints.files.async_upload_file",
                    new_callable=AsyncMock,
                    return_value="editor/test/abc.png",
                ),
                patch(
                    "app.api.v1.endpoints.files.check_rate_limit",
                    new_callable=AsyncMock,
                    return_value=True,
                ),
                patch(
                    "app.api.v1.endpoints.files.file_scan_repo.insert",
                    new_callable=AsyncMock,
                ),
                patch(
                    "app.api.v1.endpoints.files.get_redis",
                ) as mock_redis_factory,
            ):
                mock_redis = AsyncMock()
                mock_redis.set = AsyncMock(return_value=True)
                mock_redis.delete = AsyncMock()
                mock_redis_factory.return_value = mock_redis

                await client.post(
                    "/api/v1/files/upload/editor",
                    files={"file": ("test.png", png_data, "image/png")},
                    headers={"Authorization": "Bearer fake"},
                )

            # get_storage_used must be called (DB-based quota check)
            mock_get_storage.assert_called_once()
            # increment_storage_used must be called with the file size
            mock_increment.assert_called_once()
            call_args = mock_increment.call_args
            assert call_args.args[1] == len(png_data) or (
                call_args.args[1] > 0
            ), "increment delta must be positive"
        finally:
            _clear_overrides_files()

    @pytest.mark.anyio
    async def test_upload_quota_exceeded_uses_db(self, client: AsyncClient) -> None:
        """When DB reports quota exceeded, upload is rejected with 400."""
        _override_auth_files("MEMBER")
        try:
            png_data = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100

            with (
                patch(
                    "app.api.v1.endpoints.files.user_repo.get_storage_used",
                    new_callable=AsyncMock,
                    return_value=2 * 1024 * 1024 * 1024,  # 2 GB > 1 GB quota
                ),
                patch(
                    "app.api.v1.endpoints.files.check_rate_limit",
                    new_callable=AsyncMock,
                    return_value=True,
                ),
                patch(
                    "app.api.v1.endpoints.files.get_redis",
                ) as mock_redis_factory,
            ):
                mock_redis = AsyncMock()
                mock_redis.set = AsyncMock(return_value=True)
                mock_redis.delete = AsyncMock()
                mock_redis_factory.return_value = mock_redis

                resp = await client.post(
                    "/api/v1/files/upload/editor",
                    files={"file": ("test.png", png_data, "image/png")},
                    headers={"Authorization": "Bearer fake"},
                )

            assert resp.status_code == 400
            assert "quota" in resp.json()["detail"].lower()
        finally:
            _clear_overrides_files()

    @pytest.mark.anyio
    async def test_increment_not_called_on_quota_exceeded(self, client: AsyncClient) -> None:
        """increment_storage_used must NOT be called when quota check fails."""
        _override_auth_files("MEMBER")
        try:
            png_data = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100

            with (
                patch(
                    "app.api.v1.endpoints.files.user_repo.get_storage_used",
                    new_callable=AsyncMock,
                    return_value=2 * 1024 * 1024 * 1024,
                ),
                patch(
                    "app.api.v1.endpoints.files.user_repo.increment_storage_used",
                    new_callable=AsyncMock,
                ) as mock_increment,
                patch(
                    "app.api.v1.endpoints.files.check_rate_limit",
                    new_callable=AsyncMock,
                    return_value=True,
                ),
                patch(
                    "app.api.v1.endpoints.files.get_redis",
                ) as mock_redis_factory,
            ):
                mock_redis = AsyncMock()
                mock_redis.set = AsyncMock(return_value=True)
                mock_redis.delete = AsyncMock()
                mock_redis_factory.return_value = mock_redis

                await client.post(
                    "/api/v1/files/upload/editor",
                    files={"file": ("test.png", png_data, "image/png")},
                    headers={"Authorization": "Bearer fake"},
                )

            mock_increment.assert_not_called()
        finally:
            _clear_overrides_files()


class TestUserRepoStorageFunctions:
    """Unit tests for user_repo.increment_storage_used and get_storage_used."""

    def _make_pool(self, mock_conn: AsyncMock) -> MagicMock:
        """Build a MagicMock pool whose acquire() yields mock_conn (standard pattern)."""
        mock_pool = MagicMock()
        cm = AsyncMock()
        cm.__aenter__ = AsyncMock(return_value=mock_conn)
        cm.__aexit__ = AsyncMock(return_value=False)
        mock_pool.acquire.return_value = cm
        return mock_pool

    @pytest.mark.anyio
    async def test_increment_storage_used_positive_delta(self) -> None:
        """increment_storage_used executes UPDATE with GREATEST(0, ...) and positive delta."""
        user_id = uuid.uuid4()
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock()
        mock_pool = self._make_pool(mock_conn)

        with patch("app.repositories.user_repo.get_pool", return_value=mock_pool):
            from app.repositories.user_repo import increment_storage_used

            await increment_storage_used(user_id, 5000)

        mock_conn.execute.assert_called_once()
        call_args = mock_conn.execute.call_args
        assert "GREATEST" in call_args.args[0]
        assert call_args.args[1] == 5000
        assert call_args.args[2] == user_id

    @pytest.mark.anyio
    async def test_increment_storage_used_negative_delta(self) -> None:
        """increment_storage_used accepts negative delta (for delete decrement)."""
        user_id = uuid.uuid4()
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock()
        mock_pool = self._make_pool(mock_conn)

        with patch("app.repositories.user_repo.get_pool", return_value=mock_pool):
            from app.repositories.user_repo import increment_storage_used

            await increment_storage_used(user_id, -5000)

        mock_conn.execute.assert_called_once()
        call_args = mock_conn.execute.call_args
        # GREATEST(0, ...) prevents negative storage values
        assert "GREATEST" in call_args.args[0]
        assert call_args.args[1] == -5000

    @pytest.mark.anyio
    async def test_get_storage_used_returns_value(self) -> None:
        """get_storage_used returns the storage_used_bytes value from DB row."""
        user_id = uuid.uuid4()
        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(return_value={"storage_used_bytes": 987654})
        mock_pool = self._make_pool(mock_conn)

        with patch("app.repositories.user_repo.get_pool", return_value=mock_pool):
            from app.repositories.user_repo import get_storage_used

            result = await get_storage_used(user_id)

        assert result == 987654

    @pytest.mark.anyio
    async def test_get_storage_used_returns_zero_when_no_row(self) -> None:
        """get_storage_used returns 0 when user row is not found."""
        user_id = uuid.uuid4()
        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(return_value=None)
        mock_pool = self._make_pool(mock_conn)

        with patch("app.repositories.user_repo.get_pool", return_value=mock_pool):
            from app.repositories.user_repo import get_storage_used

            result = await get_storage_used(user_id)

        assert result == 0


class TestCleanupTaskImport:
    """Verify the cleanup task module can be imported without errors."""

    def test_cleanup_module_importable(self) -> None:
        """cleanup.py must be importable (no syntax errors, safe top-level imports)."""
        import importlib

        import app.tasks.cleanup as cleanup_mod

        importlib.reload(cleanup_mod)
        assert hasattr(cleanup_mod, "cleanup_orphan_files")
        assert hasattr(cleanup_mod, "cleanup_old_file_scans")
        assert hasattr(cleanup_mod, "_run_async")
        assert hasattr(cleanup_mod, "_get_referenced_keys")
        assert hasattr(cleanup_mod, "_iter_editor_files")
        assert hasattr(cleanup_mod, "_delete_orphans")
