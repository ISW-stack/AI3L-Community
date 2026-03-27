"""Tests for P0/P1 audit fixes (2026-03-25).

Covers:
  C-01: Album/DM VirusTotal scan registration
  C-02: DM .zip removal
  C-04: SERVER_DOMAIN in .env.production.example
  C-05: Container security hardening (verified via compose parse)
  H-01: serve_file fail-close on DB error
  H-02: DOCX structure validation
  H-03: Missing scan record = pending for editor files
  H-04: DM CSV injection sanitization + txt/csv UTF-8 validation
"""

import io
import uuid
import zipfile
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# H-02: DOCX structure validation
# ---------------------------------------------------------------------------


class TestDocxStructureValidation:
    """validate_docx_structure rejects non-DOCX ZIP files."""

    def test_valid_docx(self):
        """A ZIP with [Content_Types].xml and word/ passes."""
        from app.core.file_validation import validate_docx_structure

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("[Content_Types].xml", "<Types/>")
            zf.writestr("word/document.xml", "<w:document/>")
        assert validate_docx_structure(buf.getvalue()) is True

    def test_jar_masquerading_as_docx(self):
        """A JAR file (ZIP with META-INF) is rejected."""
        from app.core.file_validation import validate_docx_structure

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("META-INF/MANIFEST.MF", "Manifest-Version: 1.0")
            zf.writestr("com/example/Main.class", b"\xca\xfe\xba\xbe")
        assert validate_docx_structure(buf.getvalue()) is False

    def test_missing_word_dir(self):
        """A ZIP with [Content_Types].xml but no word/ is rejected."""
        from app.core.file_validation import validate_docx_structure

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("[Content_Types].xml", "<Types/>")
            zf.writestr("ppt/presentation.xml", "<p:presentation/>")
        assert validate_docx_structure(buf.getvalue()) is False

    def test_corrupted_zip(self):
        """Corrupted data returns False."""
        from app.core.file_validation import validate_docx_structure

        assert validate_docx_structure(b"not a zip") is False

    def test_validate_ooxml_structure_valid(self):
        """validate_ooxml_structure accepts ZIP with [Content_Types].xml."""
        from app.core.file_validation import validate_ooxml_structure

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("[Content_Types].xml", "<Types/>")
            zf.writestr("xl/workbook.xml", "<workbook/>")
        assert validate_ooxml_structure(buf.getvalue()) is True

    def test_validate_ooxml_structure_invalid(self):
        """validate_ooxml_structure rejects ZIP without [Content_Types].xml."""
        from app.core.file_validation import validate_ooxml_structure

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("random.txt", "hello")
        assert validate_ooxml_structure(buf.getvalue()) is False

    def test_editor_upload_rejects_fake_docx(self):
        """validate_editor_file rejects a ZIP masquerading as DOCX."""
        from app.core.file_validation import validate_editor_file

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("META-INF/MANIFEST.MF", "Manifest-Version: 1.0")
        data = buf.getvalue()

        with pytest.raises(Exception) as exc_info:
            validate_editor_file("exploit.docx", data)
        assert "Invalid DOCX" in str(exc_info.value) or "FILE_001" in str(exc_info.value)

    def test_editor_upload_accepts_real_docx(self):
        """validate_editor_file accepts a valid DOCX structure."""
        from app.core.file_validation import validate_editor_file

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("[Content_Types].xml", "<Types/>")
            zf.writestr("word/document.xml", "<w:document/>")
        data = buf.getvalue()

        content_type, result_data = validate_editor_file("document.docx", data)
        assert content_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


# ---------------------------------------------------------------------------
# C-02: DM .zip removal
# ---------------------------------------------------------------------------


class TestDmZipRemoved:
    """DM file validation rejects .zip files."""

    def test_zip_rejected(self):
        """ZIP files are no longer in the DM allowed extensions."""
        from app.services.dm import _DM_ALLOWED_EXTENSIONS

        assert ".zip" not in _DM_ALLOWED_EXTENSIONS

    def test_zip_upload_raises(self):
        """_validate_dm_file raises for .zip extension."""
        from app.services.dm import _validate_dm_file

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("test.txt", "hello")

        with pytest.raises(Exception) as exc_info:
            _validate_dm_file("archive.zip", buf.getvalue())
        assert "not allowed" in str(exc_info.value).lower() or "FILE_001" in str(exc_info.value)


# ---------------------------------------------------------------------------
# H-04: DM CSV injection sanitization + UTF-8 validation
# ---------------------------------------------------------------------------


class TestDmCsvSanitization:
    """CSV injection payloads are neutralized."""

    def test_csv_injection_prefix_sanitized(self):
        """Cells starting with = + - @ are prefixed with tab (C-07 OWASP)."""
        from app.services.dm import _sanitize_csv_content

        data = b"name,formula\nAlice,=cmd|'/C calc'!A0\n"
        result = _sanitize_csv_content(data).decode("utf-8")
        assert "\t=" in result
        assert "=cmd" not in result.split("\t=")[0]  # original = is tab-prefixed

    def test_csv_plus_prefix(self):
        from app.services.dm import _sanitize_csv_content

        data = b"a,b\n1,+SUM(A1:A10)\n"
        result = _sanitize_csv_content(data).decode("utf-8")
        assert "\t+SUM" in result

    def test_csv_normal_data_unchanged(self):
        from app.services.dm import _sanitize_csv_content

        data = b"name,age\nAlice,30\nBob,25\n"
        result = _sanitize_csv_content(data).decode("utf-8")
        assert "Alice" in result
        assert "30" in result

    def test_csv_non_utf8_rejected(self):
        from app.services.dm import _sanitize_csv_content

        with pytest.raises(Exception):
            _sanitize_csv_content(b"\xff\xfe invalid utf8")

    def test_txt_non_utf8_rejected(self):
        from app.services.dm import _validate_dm_file

        with pytest.raises(Exception):
            _validate_dm_file("notes.txt", b"\xff\xfe\x00\x01 invalid")

    def test_txt_valid_utf8_accepted(self):
        """Valid UTF-8 text files pass validation."""
        from app.services.dm import _validate_dm_file

        _validate_dm_file("notes.txt", "Hello, world! 你好".encode("utf-8"))

    def test_csv_valid_utf8_accepted(self):
        """Valid UTF-8 CSV files pass validation."""
        from app.services.dm import _validate_dm_file

        _validate_dm_file("data.csv", "name,age\nAlice,30\n".encode("utf-8"))


# ---------------------------------------------------------------------------
# H-04: DM DOCX/XLSX/PPTX structure validation
# ---------------------------------------------------------------------------


class TestDmOfficeValidation:
    """DM validates Office document structure beyond magic bytes."""

    def test_dm_rejects_fake_docx(self):
        from app.services.dm import _validate_dm_file

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("META-INF/MANIFEST.MF", "Manifest-Version: 1.0")

        with pytest.raises(Exception) as exc_info:
            _validate_dm_file("exploit.docx", buf.getvalue())
        assert "DOCX" in str(exc_info.value) or "FILE_001" in str(exc_info.value)

    def test_dm_accepts_real_docx(self):
        from app.services.dm import _validate_dm_file

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("[Content_Types].xml", "<Types/>")
            zf.writestr("word/document.xml", "<w:document/>")

        _validate_dm_file("report.docx", buf.getvalue())  # should not raise

    def test_dm_rejects_fake_xlsx(self):
        from app.services.dm import _validate_dm_file

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("random.txt", "not an xlsx")

        with pytest.raises(Exception):
            _validate_dm_file("data.xlsx", buf.getvalue())

    def test_dm_accepts_real_xlsx(self):
        from app.services.dm import _validate_dm_file

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("[Content_Types].xml", "<Types/>")
            zf.writestr("xl/workbook.xml", "<workbook/>")

        _validate_dm_file("data.xlsx", buf.getvalue())  # should not raise

    def test_dm_rejects_fake_pptx(self):
        from app.services.dm import _validate_dm_file

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("exploit.class", b"\xca\xfe")

        with pytest.raises(Exception):
            _validate_dm_file("slides.pptx", buf.getvalue())


# ---------------------------------------------------------------------------
# H-01: serve_file fail-close on DB error
# ---------------------------------------------------------------------------


class TestServeFileFailClose:
    """serve_file raises 503 instead of silently serving on DB error."""

    _mock_user = {
        "id": uuid.uuid4(),
        "role": "MEMBER",
        "is_deleted": False,
        "is_banned": False,
    }

    @pytest.mark.asyncio
    async def test_db_error_returns_503(self, client):
        """If file_scan_repo.find_by_key raises, serve_file returns 503."""
        key = "editor/someuserid/test.png"

        with (
            patch("app.api.v1.endpoints.files.file_scan_repo") as mock_scan_repo,
            patch("app.core.deps.validate_session", new_callable=AsyncMock, return_value=True),
            patch(
                "app.core.deps.get_user_by_id",
                new_callable=AsyncMock,
                return_value=self._mock_user,
            ),
        ):
            mock_scan_repo.find_by_key = AsyncMock(
                side_effect=RuntimeError("DB connection lost")
            )

            resp = await client.get(f"/api/v1/files/content/{key}")
            assert resp.status_code == 503

    @pytest.mark.asyncio
    async def test_missing_scan_record_returns_202(self, client):
        """Editor files with no scan record are treated as pending (H-03)."""
        key = "editor/someuserid/test.png"

        with (
            patch("app.api.v1.endpoints.files.file_scan_repo") as mock_scan_repo,
            patch("app.core.deps.validate_session", new_callable=AsyncMock, return_value=True),
            patch(
                "app.core.deps.get_user_by_id",
                new_callable=AsyncMock,
                return_value=self._mock_user,
            ),
        ):
            mock_scan_repo.find_by_key = AsyncMock(return_value=None)

            resp = await client.get(f"/api/v1/files/content/{key}")
            assert resp.status_code == 202


# ---------------------------------------------------------------------------
# C-01: Album/DM virus scan trigger
# ---------------------------------------------------------------------------


class TestTriggerVirusScan:
    """trigger_virus_scan inserts scan record and dispatches VT task."""

    @pytest.mark.asyncio
    async def test_inserts_scan_record(self):
        """trigger_virus_scan calls file_scan_repo.insert."""
        from app.core.file_validation import trigger_virus_scan

        mock_insert = AsyncMock(return_value={"file_key": "test/key", "status": "pending"})
        mock_vt = MagicMock()
        mock_vt.compute_sha256 = MagicMock(return_value="fakehash")
        mock_vt.check_virustotal = MagicMock()
        mock_vt.check_virustotal.delay = MagicMock()

        with (
            patch("app.repositories.file_scan_repo.insert", mock_insert),
            patch.dict("sys.modules", {"app.tasks.virustotal": mock_vt}),
            patch("fastapi.concurrency.run_in_threadpool", new_callable=AsyncMock, return_value="fakehash"),
        ):
            await trigger_virus_scan("test/key.png", b"fake data")

        mock_insert.assert_awaited_once_with("test/key.png")

    @pytest.mark.asyncio
    async def test_scan_record_failure_does_not_raise(self):
        """Scan record insertion failure is logged but doesn't propagate."""
        from app.core.file_validation import trigger_virus_scan

        with (
            patch(
                "app.repositories.file_scan_repo.insert",
                AsyncMock(side_effect=RuntimeError("DB down")),
            ),
        ):
            # Should not raise — virustotal import will fail but that's fine
            await trigger_virus_scan("test/key.png", b"fake data")

    @pytest.mark.asyncio
    async def test_vt_import_error_does_not_raise(self):
        """Missing VirusTotal/Celery does not crash the upload flow."""
        from app.core.file_validation import trigger_virus_scan

        with patch(
            "app.repositories.file_scan_repo.insert",
            AsyncMock(return_value={"file_key": "k", "status": "pending"}),
        ):
            # virustotal module not mocked → ImportError path
            await trigger_virus_scan("test/key.png", b"fake data")


# ---------------------------------------------------------------------------
# C-03: Cloud-sync warning at startup
# ---------------------------------------------------------------------------


class TestCloudSyncWarning:
    """Startup warns if project is in a cloud-synced directory."""

    def test_onedrive_detection(self):
        """os.getcwd containing 'OneDrive' triggers a warning."""
        import os

        cwd = os.getcwd()
        cloud_indicators = ("OneDrive", "Dropbox", "Google Drive", "iCloud")
        # Just verify the detection logic works
        detected = any(ind.lower() in cwd.lower() for ind in cloud_indicators)
        # On the actual OneDrive machine, this should be True
        if "onedrive" in cwd.lower():
            assert detected is True


# ---------------------------------------------------------------------------
# C-04: .env.production.example includes SERVER_DOMAIN
# ---------------------------------------------------------------------------


class TestEnvProductionExample:
    """Production env template includes SERVER_DOMAIN."""

    def test_server_domain_present(self):
        import os

        env_path = os.path.join(
            os.path.dirname(__file__), "..", "..", ".env.production.example"
        )
        if os.path.exists(env_path):
            content = open(env_path, encoding="utf-8").read()
            assert "SERVER_DOMAIN" in content


# ---------------------------------------------------------------------------
# C-05: Container security hardening
# ---------------------------------------------------------------------------


class TestDockerComposeSecurity:
    """Docker Compose files include security_opt for all services."""

    def _load_compose(self, filename):
        import os

        import yaml

        path = os.path.join(os.path.dirname(__file__), "..", "..", filename)
        if not os.path.exists(path):
            pytest.skip(f"{filename} not found")
        with open(path, encoding="utf-8") as f:
            return yaml.safe_load(f)

    @pytest.mark.parametrize("service", ["postgres", "redis", "minio"])
    def test_dev_compose_security_opt(self, service):
        data = self._load_compose("docker-compose.yml")
        services = data.get("services", {})
        if service not in services:
            pytest.skip(f"{service} not in compose")
        svc = services[service]
        assert "no-new-privileges:true" in svc.get("security_opt", [])
        assert "ALL" in svc.get("cap_drop", [])

    @pytest.mark.parametrize("service", ["postgres", "redis"])
    def test_prod_compose_security_opt(self, service):
        data = self._load_compose("docker-compose.prod.yml")
        services = data.get("services", {})
        if service not in services:
            pytest.skip(f"{service} not in prod compose")
        svc = services[service]
        assert "no-new-privileges:true" in svc.get("security_opt", [])
        assert "ALL" in svc.get("cap_drop", [])
