"""Tests for file upload validation — magic number check, path traversal, PDF sanitization."""

from io import BytesIO
from unittest.mock import AsyncMock, patch

from httpx import AsyncClient

from app.core.file_validation import validate_magic_number


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
