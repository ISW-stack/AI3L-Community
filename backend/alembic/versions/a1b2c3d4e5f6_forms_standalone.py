"""forms standalone — allow forms without SIG

Revision ID: a1b2c3d4e5f6
Revises: z7a8b9c0d1e2
Create Date: 2026-03-15

"""

from alembic import op

revision = "a1b2c3d4e5f6"
down_revision = "z7a8b9c0d1e2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE forms ALTER COLUMN sig_id DROP NOT NULL")
    op.execute(
        "CREATE INDEX ix_forms_standalone ON forms (created_by, created_at DESC) "
        "WHERE sig_id IS NULL AND is_deleted = false"
    )


def downgrade() -> None:
    op.execute(
        "DELETE FROM form_responses WHERE form_id IN " "(SELECT id FROM forms WHERE sig_id IS NULL)"
    )
    op.execute("DELETE FROM forms WHERE sig_id IS NULL")
    op.execute("ALTER TABLE forms ALTER COLUMN sig_id SET NOT NULL")
    op.execute("DROP INDEX IF EXISTS ix_forms_standalone")
