"""add composite indexes on dm_messages for unread count and mark_read queries

DB-07: Partial index on (conversation_id, sender_id) WHERE read_at IS NULL
       speeds up unread count queries used on every page load.
DB-08: Partial index on (conversation_id, read_at) WHERE read_at IS NULL
       speeds up mark_messages_read and find_conversations unread subquery.

Revision ID: o7p8q9r0s1t2
Revises: n6o7p8q9r0s1
Create Date: 2026-03-24
"""

from alembic import op

revision = "o7p8q9r0s1t2"
down_revision = "n6o7p8q9r0s1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # DB-07: Index for unread count query
    # Covers: SELECT COUNT(*) FROM dm_messages
    #         WHERE conversation_id = $1 AND sender_id != $2 AND read_at IS NULL
    # Also covers: count_total_unread subquery joining conversations
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_dm_messages_unread "
        "ON dm_messages (conversation_id, sender_id) "
        "WHERE read_at IS NULL"
    )

    # DB-08: Index for mark_messages_read and find_conversations unread subquery
    # Covers: UPDATE dm_messages SET read_at = NOW()
    #         WHERE conversation_id = $1 AND sender_id != $2 AND read_at IS NULL
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_dm_messages_conv_read "
        "ON dm_messages (conversation_id, read_at) "
        "WHERE read_at IS NULL"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_dm_messages_conv_read")
    op.execute("DROP INDEX IF EXISTS ix_dm_messages_unread")
