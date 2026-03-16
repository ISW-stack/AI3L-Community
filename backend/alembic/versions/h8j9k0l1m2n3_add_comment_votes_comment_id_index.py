"""Add index on comment_votes.comment_id

Revision ID: h8j9k0l1m2n3
Revises: g7h8i9j0k1l3
Create Date: 2026-03-16
"""

from alembic import op

revision = "h8j9k0l1m2n3"
down_revision = "g7h8i9j0k1l3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_comment_votes_comment_id " "ON comment_votes(comment_id)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_comment_votes_comment_id")
