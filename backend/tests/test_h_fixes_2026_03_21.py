"""Tests for HIGH audit fixes (H-02 through H-10) — 2026-03-21."""

import importlib.util
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.config import Settings

# Repo root (backend/../)
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent


# ── H-04: Production guards for POSTGRES/REDIS/MINIO passwords ───────


class TestProductionPasswordGuards:
    """H-04: docker-compose default passwords must be rejected in production."""

    _SAFE_BASE = dict(
        FASTAPI_ENV="production",
        JWT_SECRET_KEY="real_jwt_secret_key_prod_32chars_long",
        SECRET_KEY="real_secret_key_prod_32chars_long_ok",
        SUPER_ADMIN_PASSWORD="Str0ng_Admin!P@ss",
        POSTGRES_PASSWORD="real_pg_password",
        REDIS_PASSWORD="real_redis_password",
        MINIO_ROOT_PASSWORD="real_minio_password",
    )

    def test_rejects_changeme_postgres_in_production(self):
        with pytest.raises(ValueError, match="POSTGRES_PASSWORD"):
            Settings(**{**self._SAFE_BASE, "POSTGRES_PASSWORD": "changeme_postgres"})

    def test_rejects_changeme_redis_in_production(self):
        with pytest.raises(ValueError, match="REDIS_PASSWORD"):
            Settings(**{**self._SAFE_BASE, "REDIS_PASSWORD": "changeme_redis"})

    def test_rejects_changeme_minio_in_production(self):
        with pytest.raises(ValueError, match="MINIO_ROOT_PASSWORD"):
            Settings(**{**self._SAFE_BASE, "MINIO_ROOT_PASSWORD": "changeme_minio"})

    def test_allows_strong_passwords_in_production(self):
        s = Settings(**self._SAFE_BASE)
        assert s.FASTAPI_ENV == "production"

    def test_allows_changeme_in_development(self):
        s = Settings(
            FASTAPI_ENV="development",
            POSTGRES_PASSWORD="changeme_postgres",
            REDIS_PASSWORD="changeme_redis",
            MINIO_ROOT_PASSWORD="changeme_minio",
        )
        assert s.FASTAPI_ENV == "development"

    def test_rejects_bare_changeme_postgres(self):
        with pytest.raises(ValueError, match="POSTGRES_PASSWORD"):
            Settings(**{**self._SAFE_BASE, "POSTGRES_PASSWORD": "changeme"})

    def test_rejects_bare_changeme_redis(self):
        with pytest.raises(ValueError, match="REDIS_PASSWORD"):
            Settings(**{**self._SAFE_BASE, "REDIS_PASSWORD": "changeme"})

    def test_rejects_bare_changeme_minio(self):
        with pytest.raises(ValueError, match="MINIO_ROOT_PASSWORD"):
            Settings(**{**self._SAFE_BASE, "MINIO_ROOT_PASSWORD": "changeme"})


# ── H-10: Search excludes posts from deleted SIGs ────────────────────


class TestSearchDeletedSigFilter:
    """H-10: search/suggestions must not return posts from deleted SIGs."""

    @patch("app.repositories.post_repo.get_pool")
    async def test_search_query_includes_deleted_sig_filter(self, mock_get_pool, mock_pool, mock_conn):
        from app.repositories.post_repo import search

        # Return empty so we hit the count branch — simpler mocking
        mock_conn.fetch.return_value = []
        mock_conn.fetchval.return_value = 0
        mock_get_pool.return_value = mock_pool

        await search(keyword="test")

        sql = mock_conn.fetch.call_args[0][0]
        assert "sigs" in sql, "Search SQL should reference sigs table for deleted-SIG filter"
        assert "s.is_deleted" in sql, "Search SQL should filter by s.is_deleted"

    @patch("app.repositories.post_repo.get_pool")
    async def test_search_suggestions_includes_deleted_sig_filter(self, mock_get_pool, mock_pool, mock_conn):
        from app.repositories.post_repo import get_search_suggestions

        mock_conn.fetch.return_value = []
        mock_get_pool.return_value = mock_pool

        await get_search_suggestions("test")

        sql = mock_conn.fetch.call_args[0][0]
        assert "sigs" in sql
        assert "s.is_deleted" in sql

    @patch("app.repositories.post_repo.get_pool")
    async def test_keyword_suggestions_includes_deleted_sig_filter(self, mock_get_pool, mock_pool, mock_conn):
        from app.repositories.post_repo import get_keyword_suggestions

        mock_conn.fetch.return_value = []
        mock_get_pool.return_value = mock_pool

        await get_keyword_suggestions("test")

        sql = mock_conn.fetch.call_args[0][0]
        assert "sigs" in sql
        assert "s.is_deleted" in sql

    @patch("app.repositories.post_repo.get_pool")
    async def test_search_preserves_keyword_filter(self, mock_get_pool, mock_pool, mock_conn):
        from app.repositories.post_repo import search

        mock_conn.fetch.return_value = []
        mock_conn.fetchval.return_value = 0
        mock_get_pool.return_value = mock_pool

        await search(keyword="machine learning")

        sql = mock_conn.fetch.call_args[0][0]
        assert "websearch_to_tsquery" in sql
        assert "machine learning" in mock_conn.fetch.call_args[0]

    @patch("app.repositories.post_repo.get_pool")
    async def test_search_no_keyword_still_has_sig_filter(self, mock_get_pool, mock_pool, mock_conn):
        from app.repositories.post_repo import search

        mock_conn.fetch.return_value = []
        mock_conn.fetchval.return_value = 0
        mock_get_pool.return_value = mock_pool

        await search()

        sql = mock_conn.fetch.call_args[0][0]
        assert "s.is_deleted" in sql


# ── H-08 / H-09: Migration structure tests ───────────────────────────


def _load_migration(filename):
    """Load an alembic migration module by filename."""
    path = _REPO_ROOT / "backend" / "alembic" / "versions" / filename
    spec = importlib.util.spec_from_file_location(filename.replace(".py", ""), path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_H08_FILE = "h08fk320001_add_on_delete_rules_for_user_fks.py"
_H09_FILE = "h09ck320002_add_check_constraints_on_enum_columns.py"


class TestMigrationStructure:
    """Verify migration files are well-formed (no DB needed)."""

    def test_h08_migration_has_correct_revision_chain(self):
        m = _load_migration(_H08_FILE)
        assert m.revision == "h08fk320001"
        assert m.down_revision == "q8r9s0t1u2v3"

    def test_h08_migration_covers_all_required_fks(self):
        m = _load_migration(_H08_FILE)
        all_tables = [t for t, *_ in m._SET_NULL_FKS] + [t for t, *_ in m._CASCADE_FKS]
        required = [
            "posts", "comments", "audit_logs", "notifications",
            "invite_codes", "membership_applications", "forms",
            "form_responses", "post_reports", "sigs", "privacy_consents",
        ]
        for table in required:
            assert table in all_tables, f"Migration missing FK for {table}"

    def test_h08_set_null_fks_reference_users(self):
        m = _load_migration(_H08_FILE)
        for table, column, constraint, _ in m._SET_NULL_FKS:
            assert "fkey" in constraint, f"Constraint name should end with _fkey: {constraint}"

    def test_h08_cascade_tables_are_deletable(self):
        m = _load_migration(_H08_FILE)
        cascade_tables = {t for t, *_ in m._CASCADE_FKS}
        assert "privacy_consents" in cascade_tables
        assert "membership_applications" in cascade_tables

    def test_h09_migration_has_correct_revision_chain(self):
        m = _load_migration(_H09_FILE)
        assert m.revision == "h09ck320002"
        assert m.down_revision == "h08fk320001"

    def test_h09_migration_covers_all_required_tables(self):
        m = _load_migration(_H09_FILE)
        tables = [t for _, t, _ in m._CHECKS]
        required = ["users", "membership_applications", "post_reports", "sig_members", "file_scans"]
        for table in required:
            assert table in tables, f"CHECK constraint missing for {table}"

    def test_h09_users_role_check_values(self):
        m = _load_migration(_H09_FILE)
        users_check = next(expr for _, t, expr in m._CHECKS if t == "users")
        for role in ("SUPER_ADMIN", "ADMIN", "MEMBER", "GUEST"):
            assert role in users_check

    def test_h09_file_scans_status_check_values(self):
        m = _load_migration(_H09_FILE)
        fs_check = next(expr for _, t, expr in m._CHECKS if t == "file_scans")
        for status in ("pending", "clean", "malicious", "unknown", "error"):
            assert status in fs_check

    def test_h09_post_reports_status_values(self):
        m = _load_migration(_H09_FILE)
        pr_check = next(expr for _, t, expr in m._CHECKS if t == "post_reports")
        for status in ("PENDING", "RESOLVED", "DISMISSED"):
            assert status in pr_check

    def test_h09_sig_members_role_values(self):
        m = _load_migration(_H09_FILE)
        sm_check = next(expr for _, t, expr in m._CHECKS if t == "sig_members")
        for role in ("ADMIN", "SUB_ADMIN", "MEMBER"):
            assert role in sm_check


# ── H-02 + H-03: Security headers template tests ─────────────────────


class TestSecurityHeadersTemplate:
    """Verify the production security headers template is correct."""

    def _read_file(self, *parts):
        path = _REPO_ROOT / Path(*parts)
        return path.read_text(encoding="utf-8")

    def test_template_uses_minio_csp_variable(self):
        content = self._read_file("nginx", "snippets", "security-headers.conf.template")
        assert "${MINIO_CSP_ORIGIN}" in content
        assert "localhost:19000" not in content

    def test_template_includes_hsts(self):
        content = self._read_file("nginx", "snippets", "security-headers.conf.template")
        assert "Strict-Transport-Security" in content
        assert "max-age=31536000" in content

    def test_dev_headers_include_hsts(self):
        content = self._read_file("nginx", "snippets", "security-headers.conf")
        assert "Strict-Transport-Security" in content

    def test_template_has_upgrade_insecure_requests(self):
        content = self._read_file("nginx", "snippets", "security-headers.conf.template")
        assert "upgrade-insecure-requests" in content


# ── H-05: Entrypoint script tests ────────────────────────────────────


class TestNginxEntrypoint:
    """Verify the nginx entrypoint script exists and is correct."""

    def _read_entrypoint(self):
        path = _REPO_ROOT / "nginx" / "docker-entrypoint.sh"
        return path.read_text(encoding="utf-8")

    def test_entrypoint_script_exists(self):
        assert (_REPO_ROOT / "nginx" / "docker-entrypoint.sh").is_file()

    def test_entrypoint_uses_envsubst(self):
        content = self._read_entrypoint()
        assert "envsubst" in content
        assert "MINIO_CSP_ORIGIN" in content

    def test_entrypoint_checks_tls_certs(self):
        content = self._read_entrypoint()
        assert "fullchain.pem" in content
        assert "privkey.pem" in content

    def test_entrypoint_runs_nginx(self):
        content = self._read_entrypoint()
        assert "nginx" in content
        assert "daemon off" in content
