"""Fix dm_messages check constraint to allow recalled messages to have null content/attachment.

The original constraint (content IS NOT NULL OR attachment_key IS NOT NULL) blocks
the recall operation which sets both fields to NULL. The corrected constraint exempts
recalled messages: (is_recalled OR content IS NOT NULL OR attachment_key IS NOT NULL).

Revision ID: dm_recall_fix_001
Revises: a8b9c0d1e2f3
Create Date: 2026-03-27

"""

from alembic import op

revision = "dm_recall_fix_001"
down_revision = "a8b9c0d1e2f3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE dm_messages
        DROP CONSTRAINT IF EXISTS dm_messages_content_or_attachment_check
    """)
    op.execute("""
        ALTER TABLE dm_messages
        ADD CONSTRAINT dm_messages_content_or_attachment_check
        CHECK (is_recalled OR content IS NOT NULL OR attachment_key IS NOT NULL)
    """)


def downgrade() -> None:
    op.execute("""
        ALTER TABLE dm_messages
        DROP CONSTRAINT IF EXISTS dm_messages_content_or_attachment_check
    """)
    op.execute("""
        ALTER TABLE dm_messages
        ADD CONSTRAINT dm_messages_content_or_attachment_check
        CHECK (content IS NOT NULL OR attachment_key IS NOT NULL)
    """)
