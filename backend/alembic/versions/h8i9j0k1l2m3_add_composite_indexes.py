"""add composite indexes for common query patterns

Revision ID: h8i9j0k1l2m3
Revises: g7h8i9j0k1l2
Create Date: 2026-03-01 12:00:00.000000

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "h8i9j0k1l2m3"
down_revision: Union[str, None] = "g7h8i9j0k1l2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# CREATE INDEX CONCURRENTLY must run outside a transaction block.
transaction = False


def upgrade() -> None:
    op.execute("""
        CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_posts_category_created
            ON posts (category_id, created_at DESC) WHERE NOT is_deleted
        """)
    op.execute("""
        CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_posts_sig_created
            ON posts (sig_id, created_at DESC) WHERE NOT is_deleted
        """)
    op.execute("""
        CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_comments_post_created
            ON comments (post_id, created_at) WHERE NOT is_deleted
        """)
    op.execute("""
        CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_notifications_user_created
            ON notifications (user_id, created_at DESC)
        """)
    op.execute("""
        CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_audit_logs_user_created
            ON audit_logs (user_id, created_at DESC)
        """)
    op.execute("""
        CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_sig_members_sig_user
            ON sig_members (sig_id, user_id)
        """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_sig_members_sig_user")
    op.execute("DROP INDEX IF EXISTS idx_audit_logs_user_created")
    op.execute("DROP INDEX IF EXISTS idx_notifications_user_created")
    op.execute("DROP INDEX IF EXISTS idx_comments_post_created")
    op.execute("DROP INDEX IF EXISTS idx_posts_sig_created")
    op.execute("DROP INDEX IF EXISTS idx_posts_category_created")
