"""Tests for migration z7a8b9c0d1e2 — ON DELETE SET NULL for
posts.category_id and post_reports.reviewed_by FK constraints."""

import importlib.util
import types
from pathlib import Path

_MIGRATION_FILE = (
    Path(__file__).resolve().parent.parent
    / "alembic"
    / "versions"
    / "z7a8b9c0d1e2_add_on_delete_set_null_to_posts_category_id.py"
)


def _load_migration() -> types.ModuleType:
    spec = importlib.util.spec_from_file_location("migration_z7a8b9c0d1e2", _MIGRATION_FILE)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestMigrationCategoryFkExists:
    """Verify the migration module is importable and well-formed."""

    def test_migration_file_exists(self):
        assert _MIGRATION_FILE.exists(), f"Migration file not found: {_MIGRATION_FILE}"

    def test_revision_id(self):
        mod = _load_migration()
        assert mod.revision == "z7a8b9c0d1e2"

    def test_down_revision(self):
        mod = _load_migration()
        assert mod.down_revision == "y6z7a8b9c0d1"

    def test_upgrade_is_callable(self):
        mod = _load_migration()
        assert callable(mod.upgrade)

    def test_downgrade_is_callable(self):
        mod = _load_migration()
        assert callable(mod.downgrade)
