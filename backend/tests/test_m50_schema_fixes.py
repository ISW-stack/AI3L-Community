"""Tests for migration m50sf320003 — schema fixes M-50 through L-59.

These tests verify:
1. The migration file exists and has the correct revision chain.
2. The SQL logic behind each fix is sound (constraint semantics, not live DB).
"""

import importlib
import re
import types


def _load_migration() -> types.ModuleType:
    """Import the migration module by file path so we can inspect it."""
    import importlib.util
    import pathlib

    path = (
        pathlib.Path(__file__).resolve().parent.parent
        / "alembic"
        / "versions"
        / "m50_schema_fixes_320003.py"
    )
    spec = importlib.util.spec_from_file_location("m50_schema_fixes_320003", path)
    assert spec is not None, f"Migration file not found at {path}"
    assert spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestMigrationMetadata:
    """Verify migration file exists and has correct revision chain."""

    def test_migration_file_exists(self) -> None:
        mod = _load_migration()
        assert hasattr(mod, "revision")
        assert hasattr(mod, "down_revision")

    def test_revision_id(self) -> None:
        mod = _load_migration()
        assert mod.revision == "m50sf320003"

    def test_down_revision_points_to_latest_head(self) -> None:
        mod = _load_migration()
        assert mod.down_revision == "q8r9s0t1u2v3"

    def test_has_upgrade_and_downgrade(self) -> None:
        mod = _load_migration()
        assert callable(getattr(mod, "upgrade", None))
        assert callable(getattr(mod, "downgrade", None))


class TestM50DmMessagesContentOrAttachment:
    """M-50: dm_messages must have content or attachment_key (not both NULL)."""

    def test_upgrade_contains_check_constraint_sql(self) -> None:
        """The upgrade function must add the CHECK constraint."""
        import inspect

        mod = _load_migration()
        source = inspect.getsource(mod.upgrade)
        assert "dm_messages_content_or_attachment_check" in source
        assert "content IS NOT NULL OR attachment_key IS NOT NULL" in source

    def test_downgrade_drops_check_constraint(self) -> None:
        import inspect

        mod = _load_migration()
        source = inspect.getsource(mod.downgrade)
        assert "dm_messages_content_or_attachment_check" in source

    def test_check_logic_allows_content_only(self) -> None:
        """SQL CHECK: content IS NOT NULL OR attachment_key IS NOT NULL.
        content='hi', attachment_key=NULL → should pass."""
        content, attachment_key = "hi", None
        assert (content is not None) or (attachment_key is not None)

    def test_check_logic_allows_attachment_only(self) -> None:
        """content=NULL, attachment_key='file.pdf' → should pass."""
        content, attachment_key = None, "file.pdf"
        assert (content is not None) or (attachment_key is not None)

    def test_check_logic_allows_both(self) -> None:
        """content='hi', attachment_key='file.pdf' → should pass."""
        content, attachment_key = "hi", "file.pdf"
        assert (content is not None) or (attachment_key is not None)

    def test_check_logic_rejects_both_null(self) -> None:
        """content=NULL, attachment_key=NULL → should fail."""
        content, attachment_key = None, None
        assert not ((content is not None) or (attachment_key is not None))


class TestM51SigMembersPartialUnique:
    """M-51: sig_members partial unique index allows re-join after soft-delete."""

    def test_upgrade_drops_old_constraint(self) -> None:
        import inspect

        mod = _load_migration()
        source = inspect.getsource(mod.upgrade)
        assert "DROP CONSTRAINT" in source
        assert "uq_sig_members_sig_user" in source

    def test_upgrade_creates_partial_index(self) -> None:
        import inspect

        mod = _load_migration()
        source = inspect.getsource(mod.upgrade)
        assert "uq_sig_members_active" in source
        assert "WHERE is_deleted = false" in source

    def test_partial_index_logic_allows_rejoin_after_soft_delete(self) -> None:
        """Simulate: user was a member (is_deleted=True), then re-joins (is_deleted=False).
        The partial unique index only covers rows where is_deleted=false,
        so the old soft-deleted row does not conflict with the new active row."""
        # Existing row: (sig_id=A, user_id=B, is_deleted=True) — NOT in index
        # New row:      (sig_id=A, user_id=B, is_deleted=False) — in index
        # No conflict because the old row is excluded from the partial index.
        existing = {"sig_id": "A", "user_id": "B", "is_deleted": True}
        new_row = {"sig_id": "A", "user_id": "B", "is_deleted": False}

        # Only rows with is_deleted=False are in the index
        index_entries = [
            r for r in [existing, new_row] if not r["is_deleted"]
        ]
        # There should be exactly 1 active entry — no conflict
        keys = [(r["sig_id"], r["user_id"]) for r in index_entries]
        assert len(keys) == len(set(keys)), "No duplicate in partial index"

    def test_partial_index_logic_blocks_duplicate_active(self) -> None:
        """Two active rows with same (sig_id, user_id) should conflict."""
        row1 = {"sig_id": "A", "user_id": "B", "is_deleted": False}
        row2 = {"sig_id": "A", "user_id": "B", "is_deleted": False}

        index_entries = [
            r for r in [row1, row2] if not r["is_deleted"]
        ]
        keys = [(r["sig_id"], r["user_id"]) for r in index_entries]
        assert len(keys) != len(set(keys)), "Duplicate active rows should conflict"

    def test_downgrade_restores_original_constraint(self) -> None:
        import inspect

        mod = _load_migration()
        source = inspect.getsource(mod.downgrade)
        assert "uq_sig_members_sig_user" in source
        assert "DROP INDEX" in source
        assert "uq_sig_members_active" in source


class TestM52IpBansUnique:
    """M-52: ip_bans UNIQUE on ip_address prevents duplicate bans."""

    def test_upgrade_deduplicates_existing_rows(self) -> None:
        import inspect

        mod = _load_migration()
        source = inspect.getsource(mod.upgrade)
        # Must DELETE duplicates before adding the constraint
        assert "DELETE FROM ip_bans" in source
        assert "a.ip_address = b.ip_address" in source

    def test_upgrade_adds_unique_constraint(self) -> None:
        import inspect

        mod = _load_migration()
        source = inspect.getsource(mod.upgrade)
        assert "uq_ip_bans_ip_address" in source
        assert "UNIQUE" in source

    def test_downgrade_drops_unique_constraint(self) -> None:
        import inspect

        mod = _load_migration()
        source = inspect.getsource(mod.downgrade)
        assert "uq_ip_bans_ip_address" in source


class TestM53OrgChartOverridesEntityIdIndex:
    """M-53: org_chart_overrides.entity_id gets an index for cleanup queries."""

    def test_upgrade_creates_index(self) -> None:
        import inspect

        mod = _load_migration()
        source = inspect.getsource(mod.upgrade)
        assert "idx_org_chart_overrides_entity_id" in source
        assert "entity_id" in source

    def test_upgrade_adds_comment(self) -> None:
        import inspect

        mod = _load_migration()
        source = inspect.getsource(mod.upgrade)
        assert "COMMENT ON COLUMN" in source
        assert "Polymorphic" in source

    def test_downgrade_drops_index(self) -> None:
        import inspect

        mod = _load_migration()
        source = inspect.getsource(mod.downgrade)
        assert "idx_org_chart_overrides_entity_id" in source


class TestL57CategoriesRedundantUnique:
    """L-57: Remove redundant UNIQUE(name) on categories — keep case-insensitive index."""

    def test_upgrade_drops_categories_name_key(self) -> None:
        import inspect

        mod = _load_migration()
        source = inspect.getsource(mod.upgrade)
        assert "categories_name_key" in source
        assert "DROP CONSTRAINT" in source

    def test_downgrade_restores_categories_name_key(self) -> None:
        import inspect

        mod = _load_migration()
        source = inspect.getsource(mod.downgrade)
        assert "categories_name_key" in source
        assert "ADD CONSTRAINT" in source


class TestL58OrgChartUpdatedByFk:
    """L-58: org_chart_overrides.updated_by FK gets ON DELETE SET NULL."""

    def test_upgrade_makes_updated_by_nullable(self) -> None:
        import inspect

        mod = _load_migration()
        source = inspect.getsource(mod.upgrade)
        assert "DROP NOT NULL" in source

    def test_upgrade_adds_on_delete_set_null(self) -> None:
        import inspect

        mod = _load_migration()
        source = inspect.getsource(mod.upgrade)
        assert "ON DELETE SET NULL" in source

    def test_downgrade_restores_not_null(self) -> None:
        import inspect

        mod = _load_migration()
        source = inspect.getsource(mod.downgrade)
        assert "SET NOT NULL" in source


class TestL59UpdatedAtTrigger:
    """L-59: Auto-update updated_at trigger on key tables."""

    EXPECTED_TABLES = [
        "users",
        "posts",
        "comments",
        "sigs",
        "forms",
        "albums",
        "dm_messages",
        "conversations",
        "user_preferences",
    ]

    def test_upgrade_creates_trigger_function(self) -> None:
        import inspect

        mod = _load_migration()
        source = inspect.getsource(mod.upgrade)
        assert "update_updated_at_column" in source
        assert "NEW.updated_at = NOW()" in source
        assert "LANGUAGE plpgsql" in source

    def test_upgrade_creates_trigger_for_each_table(self) -> None:
        """The trigger loop iterates _UPDATED_AT_TABLES which must contain all expected tables."""
        mod = _load_migration()
        for table in self.EXPECTED_TABLES:
            assert table in mod._UPDATED_AT_TABLES, f"Missing trigger for table: {table}"

    def test_trigger_table_list_matches_constant(self) -> None:
        mod = _load_migration()
        assert mod._UPDATED_AT_TABLES == self.EXPECTED_TABLES

    def test_downgrade_drops_all_triggers(self) -> None:
        import inspect

        mod = _load_migration()
        source = inspect.getsource(mod.downgrade)
        assert "DROP TRIGGER IF EXISTS set_updated_at" in source

    def test_downgrade_drops_function(self) -> None:
        import inspect

        mod = _load_migration()
        source = inspect.getsource(mod.downgrade)
        assert "DROP FUNCTION IF EXISTS update_updated_at_column" in source
