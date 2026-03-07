"""Add unique constraint on form_responses and index.

Revision ID: p6q7r8s9t0u1
Revises: o5p6q7r8s9t0
Create Date: 2026-03-07
"""

from alembic import op

revision = "p6q7r8s9t0u1"
down_revision = "o5p6q7r8s9t0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint
                WHERE conname = 'uq_form_responses_form_user'
            ) THEN
                ALTER TABLE form_responses
                ADD CONSTRAINT uq_form_responses_form_user UNIQUE (form_id, user_id);
            END IF;
        END $$;
        """)
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_form_responses_form_created "
        "ON form_responses (form_id, created_at)"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE form_responses DROP CONSTRAINT IF EXISTS uq_form_responses_form_user")
    op.execute("DROP INDEX IF EXISTS idx_form_responses_form_created")
