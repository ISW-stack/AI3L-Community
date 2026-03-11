"""Add composite index on form_responses(form_id, user_id) and partial index on comments(user_id).

Revision ID: u2v3w4x5y6z7
Revises: t1u2v3w4x5y6
Create Date: 2026-03-11
"""

from alembic import op

revision = "u2v3w4x5y6z7"
down_revision = "t1u2v3w4x5y6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_form_responses_form_user "
        "ON form_responses(form_id, user_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_comments_user_id "
        "ON comments(user_id) WHERE is_deleted = FALSE"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_comments_user_id")
    op.execute("DROP INDEX IF EXISTS ix_form_responses_form_user")
