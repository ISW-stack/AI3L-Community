"""Tests for file upload validation — magic number check, path traversal, PDF sanitization."""

import uuid
from io import BytesIO
from unittest.mock import AsyncMock, patch

import pytest
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

    def test_sanitize_strips_javascript(self):
        from pypdf import PdfWriter
        from pypdf.generic import NameObject, TextStringObject

        from app.core.file_validation import sanitize_pdf

        # Create a PDF with an OpenAction
        writer = PdfWriter()
        writer.add_blank_page(width=200, height=200)
        writer._root_object[NameObject("/OpenAction")] = TextStringObject("alert('xss')")

        buf = BytesIO()
        writer.write(buf)
        raw = buf.getvalue()

        sanitized = sanitize_pdf(raw)
        assert len(sanitized) > 0
        # The sanitized PDF should not contain the dangerous key
        assert b"/OpenAction" not in sanitized
