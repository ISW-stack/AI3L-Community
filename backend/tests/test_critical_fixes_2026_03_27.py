"""Tests for Critical security fixes (C-01 through C-07) from production audit 2026-03-27.

C-01: Form max_respondents — CTE+FOR UPDATE belt-and-suspenders
C-02: File ownership validation — removed fallback bypass
C-05: .env not in git history (verified manually)
C-06: FASTAPI_DEBUG blocked in production
C-07: CSV injection tab-prefix sanitization
"""

import uuid

import pytest


# ---------------------------------------------------------------------------
# C-01: Form max_respondents — CTE + FOR UPDATE in INSERT
# ---------------------------------------------------------------------------


class TestFormMaxRespondentsCTE:
    """C-01: create_response uses CTE with FOR UPDATE to prevent over-insertion."""

    @pytest.mark.anyio
    async def test_insert_under_limit_succeeds(self):
        """When count < max, INSERT returns a row (truthy)."""
        from unittest.mock import AsyncMock, MagicMock, patch

        from app.repositories.form_repo import insert_response

        form_id = uuid.uuid4()
        response_id = uuid.uuid4()

        conn = AsyncMock()
        # Advisory lock succeeds
        conn.execute = AsyncMock(return_value="SELECT 1")
        # fetchrow returns a row (INSERT succeeded)
        conn.fetchrow = AsyncMock(return_value={"id": response_id})

        result = await insert_response(
            conn=conn,
            response_id=response_id,
            form_id=form_id,
            user_id=uuid.uuid4(),
            answers={"q1": "answer"},
            max_respondents=100,
            guest_allowed=False,
        )

        assert result is True
        # Verify CTE SQL was used (fetchrow, not execute)
        sql = conn.fetchrow.call_args[0][0]
        assert "WITH cur AS" in sql
        assert "FOR UPDATE" in sql
        assert "cur.cnt < $5" in sql

    @pytest.mark.anyio
    async def test_insert_at_limit_returns_false(self):
        """When count >= max, INSERT returns no row (None)."""
        from unittest.mock import AsyncMock, MagicMock, patch

        from app.repositories.form_repo import insert_response

        form_id = uuid.uuid4()
        response_id = uuid.uuid4()

        conn = AsyncMock()
        conn.execute = AsyncMock(return_value="SELECT 1")
        # fetchrow returns None (INSERT didn't happen — limit reached)
        conn.fetchrow = AsyncMock(return_value=None)

        result = await insert_response(
            conn=conn,
            response_id=response_id,
            form_id=form_id,
            user_id=uuid.uuid4(),
            answers={"q1": "answer"},
            max_respondents=100,
            guest_allowed=False,
        )

        assert result is False

    @pytest.mark.anyio
    async def test_insert_without_max_uses_plain_insert(self):
        """When max_respondents is None, plain INSERT is used (no CTE)."""
        from unittest.mock import AsyncMock, MagicMock, patch

        from app.repositories.form_repo import insert_response

        form_id = uuid.uuid4()
        response_id = uuid.uuid4()

        conn = AsyncMock()
        conn.execute = AsyncMock(return_value="INSERT 0 1")

        result = await insert_response(
            conn=conn,
            response_id=response_id,
            form_id=form_id,
            user_id=uuid.uuid4(),
            answers={"q1": "answer"},
            max_respondents=None,
            guest_allowed=False,
        )

        assert result is True
        # Plain execute, not fetchrow
        sql = conn.execute.call_args[0][0]
        assert "WITH cur AS" not in sql


# ---------------------------------------------------------------------------
# C-02: File ownership validation — no fallback bypass
# ---------------------------------------------------------------------------


class TestFileOwnershipNoFallback:
    """C-02: _validate_file_ownership rejects path with user_id in wrong position."""

    def test_user_id_in_filename_segment_rejected(self):
        """Attacker embedding their UUID in filename is rejected."""
        from app.services.form import _validate_file_ownership

        attacker_id = str(uuid.uuid4())
        victim_id = str(uuid.uuid4())
        # Attacker puts their own ID in the filename part of victim's path
        questions = [{"id": "q1", "type": "file_upload", "label": "Doc"}]
        answers = {
            "q1": {
                "key": f"editor/{victim_id}/{attacker_id}_malicious.pdf",
                "filename": f"{attacker_id}_malicious.pdf",
            }
        }

        with pytest.raises(PermissionError, match="does not belong"):
            _validate_file_ownership(questions, answers, attacker_id)

    def test_user_id_in_arbitrary_position_rejected(self):
        """user_id appearing in an unexpected path position is rejected."""
        from app.services.form import _validate_file_ownership

        user_id = str(uuid.uuid4())
        other_id = str(uuid.uuid4())
        questions = [{"id": "q1", "type": "file_upload", "label": "Doc"}]
        # user_id in position 4 (after forms/uploads/form_id) should be valid
        # but user_id in a totally wrong structure should not
        answers = {
            "q1": {
                "key": f"unknown/{other_id}/{user_id}/file.pdf",
                "filename": "file.pdf",
            }
        }

        with pytest.raises(PermissionError, match="does not belong"):
            _validate_file_ownership(questions, answers, user_id)

    def test_editor_path_correct_position_accepted(self):
        """editor/{user_id}/{filename} is accepted."""
        from app.services.form import _validate_file_ownership

        user_id = str(uuid.uuid4())
        questions = [{"id": "q1", "type": "file_upload", "label": "Doc"}]
        answers = {"q1": {"key": f"editor/{user_id}/file.pdf", "filename": "file.pdf"}}

        _validate_file_ownership(questions, answers, user_id)

    def test_forms_uploads_path_correct_position_accepted(self):
        """forms/uploads/{form_id}/{user_id}/{filename} is accepted."""
        from app.services.form import _validate_file_ownership

        user_id = str(uuid.uuid4())
        form_id = str(uuid.uuid4())
        questions = [{"id": "q1", "type": "file_upload", "label": "Doc"}]
        answers = {
            "q1": {
                "key": f"forms/uploads/{form_id}/{user_id}/file.pdf",
                "filename": "file.pdf",
            }
        }

        _validate_file_ownership(questions, answers, user_id)

    def test_forms_path_correct_position_accepted(self):
        """forms/{form_id}/{user_id}/{filename} is accepted."""
        from app.services.form import _validate_file_ownership

        user_id = str(uuid.uuid4())
        form_id = str(uuid.uuid4())
        questions = [{"id": "q1", "type": "file_upload", "label": "Doc"}]
        answers = {
            "q1": {
                "key": f"forms/{form_id}/{user_id}/file.pdf",
                "filename": "file.pdf",
            }
        }

        _validate_file_ownership(questions, answers, user_id)

    def test_other_users_editor_path_rejected(self):
        """editor/{other_user_id}/{filename} is rejected."""
        from app.services.form import _validate_file_ownership

        user_id = str(uuid.uuid4())
        other_id = str(uuid.uuid4())
        questions = [{"id": "q1", "type": "file_upload", "label": "Doc"}]
        answers = {"q1": {"key": f"editor/{other_id}/file.pdf", "filename": "file.pdf"}}

        with pytest.raises(PermissionError, match="does not belong"):
            _validate_file_ownership(questions, answers, user_id)


# ---------------------------------------------------------------------------
# C-06: FASTAPI_DEBUG blocked in production
# ---------------------------------------------------------------------------


class TestDebugBlockedInProduction:
    """C-06: FASTAPI_DEBUG=True raises ValueError in production."""

    def _make_settings(self, **overrides):
        from pydantic_settings import SettingsConfigDict

        from app.core.config import Settings

        class TestSettingsClass(Settings):
            model_config = SettingsConfigDict(env_file=None, extra="ignore")

        return TestSettingsClass(**overrides)

    def test_debug_true_in_production_raises(self):
        """Production with FASTAPI_DEBUG=True must not start."""
        with pytest.raises(ValueError, match="FASTAPI_DEBUG"):
            self._make_settings(
                FASTAPI_ENV="production",
                FASTAPI_DEBUG=True,
                JWT_SECRET_KEY="a_real_production_secret_key_here",
                SECRET_KEY="real_secret_key_prod_32chars_long_ok",
                SUPER_ADMIN_PASSWORD="strong_p@ssw0rd!",
                POSTGRES_PASSWORD="real_pg_password",
                REDIS_PASSWORD="real_redis_password",
                S3_SECRET_ACCESS_KEY="real_minio_password",
                S3_ACCESS_KEY_ID="real_access_key",
                CORS_ORIGINS="https://example.com",
            )

    def test_debug_false_in_production_ok(self):
        """Production with FASTAPI_DEBUG=False starts successfully."""
        s = self._make_settings(
            FASTAPI_ENV="production",
            FASTAPI_DEBUG=False,
            JWT_SECRET_KEY="a_real_production_secret_key_here",
            SECRET_KEY="real_secret_key_prod_32chars_long_ok",
            SUPER_ADMIN_PASSWORD="strong_p@ssw0rd!",
            POSTGRES_PASSWORD="real_pg_password",
            REDIS_PASSWORD="real_redis_password",
            S3_SECRET_ACCESS_KEY="real_minio_password",
            S3_ACCESS_KEY_ID="real_access_key",
            CORS_ORIGINS="https://example.com",
        )
        assert s.FASTAPI_DEBUG is False

    def test_debug_true_in_development_allowed(self):
        """Development with FASTAPI_DEBUG=True is allowed."""
        s = self._make_settings(FASTAPI_ENV="development", FASTAPI_DEBUG=True)
        assert s.FASTAPI_DEBUG is True


# ---------------------------------------------------------------------------
# C-07: CSV injection — tab prefix sanitization
# ---------------------------------------------------------------------------


class TestCsvTabPrefixSanitization:
    """C-07: _sanitize_csv_content uses tab prefix per OWASP recommendation."""

    def test_equals_prefix_gets_tab(self):
        from app.services.dm import _sanitize_csv_content

        data = b'name,val\nAlice,=1+1\n'
        result = _sanitize_csv_content(data).decode("utf-8")
        # Tab prefix instead of apostrophe
        assert "\t=" in result

    def test_at_prefix_gets_tab(self):
        from app.services.dm import _sanitize_csv_content

        data = b"a,b\nx,@SUM(A1)\n"
        result = _sanitize_csv_content(data).decode("utf-8")
        assert "\t@" in result

    def test_minus_prefix_gets_tab(self):
        from app.services.dm import _sanitize_csv_content

        data = b"a,b\nx,-cmd\n"
        result = _sanitize_csv_content(data).decode("utf-8")
        assert "\t-" in result

    def test_quoted_formula_also_sanitized(self):
        """CSV reader strips quotes before our check, so '=\"1+1\"' is caught."""
        import csv
        from io import StringIO

        from app.services.dm import _sanitize_csv_content

        # Build CSV with quoted formula cell
        buf = StringIO()
        writer = csv.writer(buf)
        writer.writerow(["name", "formula"])
        writer.writerow(["Alice", '=1+1'])
        csv_bytes = buf.getvalue().encode("utf-8")

        result = _sanitize_csv_content(csv_bytes).decode("utf-8")
        reader = csv.reader(StringIO(result))
        rows = list(reader)
        # The formula cell should start with tab
        assert rows[1][1].startswith("\t")

    def test_normal_data_unmodified(self):
        from app.services.dm import _sanitize_csv_content

        data = b"name,age\nAlice,30\nBob,25\n"
        result = _sanitize_csv_content(data).decode("utf-8")
        assert "Alice" in result
        assert "30" in result
        # No tab prefix on normal data
        assert "\tAlice" not in result
        assert "\t30" not in result

    def test_idempotent_no_double_prefix(self):
        """Sanitizing already-sanitized CSV must not add extra tabs."""
        from app.services.dm import _sanitize_csv_content

        data = b"a,b\nx,=formula\n"
        once = _sanitize_csv_content(data)
        twice = _sanitize_csv_content(once)
        assert once == twice, "Double-sanitization should be idempotent"

    def test_leading_whitespace_formula_not_stripped(self):
        """Cells with leading spaces before formula chars are left as-is."""
        from app.services.dm import _sanitize_csv_content

        data = b"a,b\nx, =formula\n"
        result = _sanitize_csv_content(data).decode("utf-8")
        # Space before = means it won't be evaluated by spreadsheets
        assert "\t" not in result or "\t " not in result

    def test_non_utf8_rejected(self):
        from app.services.dm import _sanitize_csv_content

        with pytest.raises(Exception):
            _sanitize_csv_content(b"\xff\xfe invalid")
