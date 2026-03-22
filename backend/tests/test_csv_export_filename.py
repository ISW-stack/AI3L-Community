"""Tests for CSV export filename handling: storage.py and form_export.py.

Covers the double-encoding fix in generate_presigned_url and the ASCII-only
filename sanitization in form_export._async_export.
"""

import json
import sys
import types
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Celery mock (same pattern as test_celery_tasks.py)
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _celery_modules():
    """Inject fake celery modules so form_export can be imported."""
    celery_mod = types.ModuleType("celery")
    celery_result_mod = types.ModuleType("celery.result")
    celery_mod.result = celery_result_mod
    celery_mod.shared_task = lambda **kw: (lambda fn: fn)

    celery_app_mod = types.ModuleType("app.celery_app")
    mock_celery_app = MagicMock()
    mock_celery_app.task = lambda *a, **kw: (lambda fn: fn)
    celery_app_mod.celery = mock_celery_app

    saved = {}
    for mod_name, mod_obj in [
        ("celery", celery_mod),
        ("celery.result", celery_result_mod),
        ("app.celery_app", celery_app_mod),
    ]:
        saved[mod_name] = sys.modules.get(mod_name)
        sys.modules[mod_name] = mod_obj

    yield

    for mod_name, prev in saved.items():
        if prev is None:
            sys.modules.pop(mod_name, None)
        else:
            sys.modules[mod_name] = prev


# ===========================================================================
# 1. generate_presigned_url — Content-Disposition tests
# ===========================================================================


class TestPresignedUrlContentDisposition:
    """Verify generate_presigned_url builds correct Content-Disposition (no double-encoding)."""

    def _call(self, filename: str | None = None) -> dict:
        """Call generate_presigned_url and capture the Params passed to boto3."""
        from app.core.storage import generate_presigned_url

        mock_client = MagicMock()
        mock_client.generate_presigned_url.return_value = "https://example.com/signed"

        captured_params: dict = {}

        def capture(method, Params=None, ExpiresIn=3600):
            captured_params.update(Params or {})
            return "https://example.com/signed"

        mock_client.generate_presigned_url.side_effect = capture

        with (
            patch("app.core.storage._s3_presign_client", None),
            patch("app.core.storage.get_storage", return_value=mock_client),
            patch("app.core.storage.settings") as mock_settings,
        ):
            mock_settings.S3_BUCKET_NAME = "test-bucket"
            generate_presigned_url("test-key", filename=filename)

        return captured_params

    def test_ascii_filename(self):
        """ASCII filename produces simple Content-Disposition without encoding."""
        params = self._call("report.csv")
        disposition = params.get("ResponseContentDisposition", "")
        assert 'attachment; filename="report.csv"' == disposition
        # No percent-encoding should be present
        assert "%" not in disposition

    def test_unicode_filename_no_double_encoding(self):
        """Unicode filename should NOT be percent-encoded in the disposition value.

        Previously the code called urllib.parse.quote() which boto3 would then
        double-encode (e.g. %E4 -> %25E4).  After the fix, only the ASCII
        fallback is used, so no percent signs should appear.
        """
        params = self._call("\u8abf\u67e5\u8868.csv")  # 調查表.csv
        disposition = params.get("ResponseContentDisposition", "")
        # Should use ASCII fallback; no percent signs
        assert disposition.startswith("attachment; filename=")
        assert "%25" not in disposition  # no double-encoding
        assert "%E" not in disposition.upper()  # no pre-encoding at all

    def test_unicode_filename_ascii_fallback(self):
        """Unicode chars in filename are replaced with _ in the ASCII fallback."""
        params = self._call("\u8abf\u67e5\u8868.csv")
        disposition = params.get("ResponseContentDisposition", "")
        # ASCII fallback replaces non-ASCII with _
        assert 'filename="' in disposition
        assert disposition.endswith('"')
        # Extract the fallback name
        name = disposition.split('filename="')[1].rstrip('"')
        assert name.endswith(".csv")
        # All chars in name should be ASCII printable
        assert all(0x20 <= ord(c) <= 0x7E for c in name)

    def test_special_characters_in_filename(self):
        """Special chars within ASCII range are kept in fallback."""
        params = self._call("my report (2026).csv")
        disposition = params.get("ResponseContentDisposition", "")
        assert 'attachment; filename="my report (2026).csv"' == disposition

    def test_empty_filename_skips_disposition(self):
        """Empty filename should not set ResponseContentDisposition."""
        params = self._call("")
        assert "ResponseContentDisposition" not in params

    def test_none_filename_skips_disposition(self):
        """None filename should not set ResponseContentDisposition."""
        params = self._call(None)
        assert "ResponseContentDisposition" not in params

    def test_only_non_ascii_chars_fallback_to_export(self):
        """If filename base is entirely non-ASCII, fallback to 'export'."""
        params = self._call("\u4e2d\u6587.csv")  # 中文.csv
        disposition = params.get("ResponseContentDisposition", "")
        assert 'attachment; filename="export.csv"' == disposition

    def test_mixed_ascii_unicode_filename(self):
        """Mixed ASCII/Unicode filename keeps ASCII chars, replaces others."""
        params = self._call("Survey\u8abf\u67e5Data.csv")
        disposition = params.get("ResponseContentDisposition", "")
        name = disposition.split('filename="')[1].rstrip('"')
        assert name.endswith(".csv")
        # Should contain "Survey" and "Data" with underscores between
        assert "Survey" in name
        assert "Data" in name


# ===========================================================================
# 2. form_export filename sanitization — ASCII-only
# ===========================================================================


class TestFormExportFilenameSanitization:
    """Verify form_export produces ASCII-only filenames."""

    def _make_form_row(self, title: str):
        return {
            "questions": json.dumps([{"id": "q1", "label": "Q"}]),
            "title": title,
        }

    def _make_pool(self, form_row):
        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(return_value=form_row)
        mock_conn.fetch = AsyncMock(return_value=[])

        mock_cm = AsyncMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_cm.__aexit__ = AsyncMock(return_value=False)

        mock_pool = MagicMock()
        mock_pool.acquire = MagicMock(return_value=mock_cm)
        return mock_pool

    async def _run_export(self, title: str) -> str:
        """Run _async_export and return the filename passed to generate_presigned_url."""
        form_row = self._make_form_row(title)
        mock_pool = self._make_pool(form_row)

        captured_filename = {}

        def capture_presigned(key, expires_in=3600, filename=None):
            captured_filename["value"] = filename
            return "https://example.com/signed"

        with (
            patch("app.tasks.form_export.get_pool", return_value=mock_pool),
            patch("app.core.storage.get_storage", return_value=MagicMock()),
            patch("app.tasks.form_export.upload_file"),
            patch(
                "app.tasks.form_export.generate_presigned_url",
                side_effect=capture_presigned,
            ),
            patch(
                "app.tasks.form_export.generate_form_export_key",
                return_value="exports/test.csv",
            ),
        ):
            from app.tasks.form_export import _async_export

            await _async_export(str(uuid.uuid4()), "task-1")

        return captured_filename["value"]

    @pytest.mark.anyio
    async def test_ascii_title_preserved(self):
        """ASCII form title is preserved in the filename."""
        filename = await self._run_export("My Survey")
        assert filename == "My_Survey.csv"

    @pytest.mark.anyio
    async def test_unicode_title_stripped(self):
        r"""Non-ASCII chars in form title are stripped (not just \w-matched)."""
        filename = await self._run_export("\u8abf\u67e5\u8868\u55ae")  # 調查表單
        # All non-ASCII stripped → falls back to "export"
        assert filename == "export.csv"

    @pytest.mark.anyio
    async def test_mixed_title_keeps_ascii(self):
        """Mixed ASCII/Unicode title keeps only ASCII portion."""
        filename = await self._run_export("Survey\u8abf\u67e5 2026")
        assert filename == "Survey_2026.csv"

    @pytest.mark.anyio
    async def test_special_chars_stripped(self):
        """Special punctuation like ()!@# is stripped from title."""
        filename = await self._run_export("My Form! (v2.0) @test")
        # Only a-zA-Z0-9_ spaces and hyphens survive
        assert filename == "My_Form_v20_test.csv"

    @pytest.mark.anyio
    async def test_empty_title_fallback(self):
        """Empty title falls back to 'export'."""
        filename = await self._run_export("")
        assert filename == "export.csv"

    @pytest.mark.anyio
    async def test_whitespace_only_title_fallback(self):
        """Whitespace-only title falls back to 'export'."""
        filename = await self._run_export("   ")
        assert filename == "export.csv"

    @pytest.mark.anyio
    async def test_title_truncated_at_80_chars(self):
        """Titles longer than 80 chars are truncated."""
        long_title = "A" * 100
        filename = await self._run_export(long_title)
        # 80 chars + .csv = 84 chars total
        assert len(filename) == 84
        assert filename == "A" * 80 + ".csv"

    @pytest.mark.anyio
    async def test_hyphens_preserved(self):
        """Hyphens in title are preserved."""
        filename = await self._run_export("Pre-Survey Data")
        assert filename == "Pre-Survey_Data.csv"

    @pytest.mark.anyio
    async def test_underscores_preserved(self):
        """Underscores in title are preserved."""
        filename = await self._run_export("my_form_v2")
        assert filename == "my_form_v2.csv"

    @pytest.mark.anyio
    async def test_filename_is_all_ascii(self):
        """Regardless of input, the resulting filename is pure ASCII."""
        titles = [
            "\u4e2d\u6587\u8868\u55ae",
            "\u65e5\u672c\u8a9e\u30c6\u30b9\u30c8",
            "\ud55c\uad6d\uc5b4 \ud14c\uc2a4\ud2b8",
            "\u00e9\u00e8\u00ea\u00eb",
            "Caf\u00e9 Survey",
            "R\u00e9sum\u00e9 Form",
        ]
        for title in titles:
            filename = await self._run_export(title)
            assert filename.isascii(), f"Non-ASCII in filename for title {title!r}: {filename}"
            assert filename.endswith(".csv")
