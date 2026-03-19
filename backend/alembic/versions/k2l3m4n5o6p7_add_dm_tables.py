"""add DM conversations and messages tables

Revision ID: k2l3m4n5o6p7
Revises: j1k2l3m4n5o6
Create Date: 2026-03-17

"""

import sqlalchemy as sa

from alembic import op

revision = "k2l3m4n5o6p7"
down_revision = "j1k2l3m4n5o6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── conversations table ──
    op.execute("""
        CREATE TABLE conversations (
            id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            participant_a UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            participant_b UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            total_chars INT NOT NULL DEFAULT 0,
            created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT uq_conversation_pair UNIQUE (participant_a, participant_b),
            CONSTRAINT ck_participant_order CHECK (participant_a < participant_b),
            CONSTRAINT ck_no_self_convo CHECK (participant_a != participant_b)
        )
        """)
    op.create_index("ix_conversations_participant_a", "conversations", ["participant_a"])
    op.create_index("ix_conversations_participant_b", "conversations", ["participant_b"])

    # ── dm_messages table ──
    op.execute("""
        CREATE TABLE dm_messages (
            id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            conversation_id     UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
            sender_id           UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            content             TEXT,
            attachment_key      TEXT,
            attachment_name     TEXT,
            attachment_size     INT,
            attachment_expires_at TIMESTAMPTZ,
            is_recalled         BOOLEAN NOT NULL DEFAULT FALSE,
            is_edited           BOOLEAN NOT NULL DEFAULT FALSE,
            read_at             TIMESTAMPTZ,
            created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """)
    op.create_index(
        "ix_dm_messages_conversation_created",
        "dm_messages",
        ["conversation_id", sa.text("created_at DESC")],
    )
    op.create_index("ix_dm_messages_sender_id", "dm_messages", ["sender_id"])
    op.execute("""
        CREATE INDEX ix_dm_messages_attachment_expires
        ON dm_messages (attachment_expires_at)
        WHERE attachment_expires_at IS NOT NULL
        """)
    op.execute("""
        CREATE INDEX ix_dm_messages_text_cleanup
        ON dm_messages (created_at)
        WHERE NOT is_recalled
        """)

    # ── user_preferences: add dm_friends_only column ──
    op.add_column(
        "user_preferences",
        sa.Column("dm_friends_only", sa.Boolean(), nullable=False, server_default=sa.text("FALSE")),
    )


def downgrade() -> None:
    op.drop_column("user_preferences", "dm_friends_only")
    op.drop_table("dm_messages")
    op.drop_table("conversations")
