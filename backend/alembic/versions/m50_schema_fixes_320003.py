"""Schema fixes: M-50, M-51, M-52, M-53, L-57, L-58, L-59.

M-50: dm_messages must have content or attachment (not both NULL)
M-51: sig_members unique constraint → partial unique index (allow re-join after soft-delete)
M-52: ip_bans deduplicate + add UNIQUE on ip_address
M-53: org_chart_overrides index on entity_id for cleanup queries
L-57: categories remove redundant UNIQUE(name) (keep case-insensitive index)
L-58: org_chart_overrides updated_by FK ON DELETE SET NULL + make nullable
L-59: updated_at auto-trigger on key tables

Revision ID: m50sf320003
Revises: q8r9s0t1u2v3
Create Date: 2026-03-21
"""

from alembic import op

revision = "m50sf320003"
down_revision = "q8r9s0t1u2v3"
branch_labels = None
depends_on = None

# Tables that have an updated_at column and should get the auto-update trigger.
_UPDATED_AT_TABLES = [
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


def upgrade() -> None:
    # ── M-50: dm_messages must have content OR attachment ──
    op.execute("""
        ALTER TABLE dm_messages
        ADD CONSTRAINT dm_messages_content_or_attachment_check
        CHECK (content IS NOT NULL OR attachment_key IS NOT NULL)
    """)

    # ── M-51: sig_members partial unique index for soft-delete re-join ──
    # Drop the old unique constraint that blocks re-join after soft-delete.
    op.execute("""
        ALTER TABLE sig_members
        DROP CONSTRAINT IF EXISTS uq_sig_members_sig_user
    """)
    # Add a partial unique index: only active (non-deleted) rows are unique.
    op.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS uq_sig_members_active
        ON sig_members (sig_id, user_id) WHERE is_deleted = false
    """)

    # ── M-52: ip_bans deduplicate + UNIQUE on ip_address ──
    # Remove duplicates, keeping the row with the latest created_at.
    op.execute("""
        DELETE FROM ip_bans a
        USING ip_bans b
        WHERE a.id < b.id AND a.ip_address = b.ip_address
    """)
    op.execute("""
        ALTER TABLE ip_bans
        ADD CONSTRAINT uq_ip_bans_ip_address UNIQUE (ip_address)
    """)

    # ── M-53: org_chart_overrides index on entity_id ──
    # entity_id is a polymorphic reference (user or SIG) so FK is not possible.
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_org_chart_overrides_entity_id
        ON org_chart_overrides (entity_id)
    """)
    op.execute("""
        COMMENT ON COLUMN org_chart_overrides.entity_id IS
        'Polymorphic UUID — references either users.id or sigs.id. No FK constraint by design.'
    """)

    # ── L-57: categories remove redundant UNIQUE(name) ──
    # The original migration created UNIQUE(name) (case-sensitive).
    # A later migration added uq_categories_name on LOWER(name) (case-insensitive).
    # The case-insensitive index subsumes the original, so drop the constraint.
    op.execute("""
        ALTER TABLE categories
        DROP CONSTRAINT IF EXISTS categories_name_key
    """)

    # ── L-58: org_chart_overrides updated_by FK ON DELETE SET NULL ──
    # Make updated_by nullable first (it was NOT NULL).
    op.execute("""
        ALTER TABLE org_chart_overrides
        ALTER COLUMN updated_by DROP NOT NULL
    """)
    op.execute("""
        ALTER TABLE org_chart_overrides
        DROP CONSTRAINT IF EXISTS org_chart_overrides_updated_by_fkey
    """)
    op.execute("""
        ALTER TABLE org_chart_overrides
        ADD CONSTRAINT org_chart_overrides_updated_by_fkey
        FOREIGN KEY (updated_by) REFERENCES users(id) ON DELETE SET NULL
    """)

    # ── L-59: updated_at auto-trigger ──
    op.execute("""
        CREATE OR REPLACE FUNCTION update_updated_at_column()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = NOW();
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
    """)
    for table in _UPDATED_AT_TABLES:
        op.execute(f"""
            CREATE TRIGGER set_updated_at
            BEFORE UPDATE ON {table}
            FOR EACH ROW EXECUTE FUNCTION update_updated_at_column()
        """)


def downgrade() -> None:
    # ── L-59: drop triggers + function ──
    for table in reversed(_UPDATED_AT_TABLES):
        op.execute(f"DROP TRIGGER IF EXISTS set_updated_at ON {table}")
    op.execute("DROP FUNCTION IF EXISTS update_updated_at_column()")

    # ── L-58: restore original FK (no ON DELETE) and NOT NULL ──
    op.execute("""
        ALTER TABLE org_chart_overrides
        DROP CONSTRAINT IF EXISTS org_chart_overrides_updated_by_fkey
    """)
    op.execute("""
        ALTER TABLE org_chart_overrides
        ADD CONSTRAINT org_chart_overrides_updated_by_fkey
        FOREIGN KEY (updated_by) REFERENCES users(id)
    """)
    op.execute("""
        ALTER TABLE org_chart_overrides
        ALTER COLUMN updated_by SET NOT NULL
    """)

    # ── L-57: re-add original UNIQUE(name) on categories ──
    op.execute("""
        ALTER TABLE categories
        ADD CONSTRAINT categories_name_key UNIQUE (name)
    """)

    # ── M-53: drop entity_id index ──
    op.execute("DROP INDEX IF EXISTS idx_org_chart_overrides_entity_id")
    op.execute("COMMENT ON COLUMN org_chart_overrides.entity_id IS NULL")

    # ── M-52: drop ip_bans unique constraint ──
    op.execute("""
        ALTER TABLE ip_bans
        DROP CONSTRAINT IF EXISTS uq_ip_bans_ip_address
    """)

    # ── M-51: drop partial index, re-add original unique constraint ──
    op.execute("DROP INDEX IF EXISTS uq_sig_members_active")
    op.execute("""
        ALTER TABLE sig_members
        ADD CONSTRAINT uq_sig_members_sig_user UNIQUE (sig_id, user_id)
    """)

    # ── M-50: drop dm_messages check ──
    op.execute("""
        ALTER TABLE dm_messages
        DROP CONSTRAINT IF EXISTS dm_messages_content_or_attachment_check
    """)
