"""Add performance indexes for notifications and post_history.

Revision ID: q7r8s9t0u1v2
Revises: p6q7r8s9t0u1
Create Date: 2026-03-08

"""

from alembic import op

revision = "q7r8s9t0u1v2"
down_revision = "p6q7r8s9t0u1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_notifications_user_is_read "
        "ON notifications (user_id, is_read) WHERE is_read = false"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_post_history_post_version "
        "ON post_history (post_id, version DESC)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_post_history_post_version")
    op.execute("DROP INDEX IF EXISTS idx_notifications_user_is_read")
