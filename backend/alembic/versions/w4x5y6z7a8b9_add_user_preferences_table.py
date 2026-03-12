"""add user_preferences table

Revision ID: w4x5y6z7a8b9
Revises: v3w4x5y6z7a8
Create Date: 2026-03-12

"""

import sqlalchemy as sa

from alembic import op

revision = "w4x5y6z7a8b9"
down_revision = "v3w4x5y6z7a8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE user_preferences (
            user_id UUID PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
            theme VARCHAR(10) NOT NULL DEFAULT 'light',
            notify_mentions BOOLEAN NOT NULL DEFAULT TRUE,
            notify_replies BOOLEAN NOT NULL DEFAULT TRUE,
            notify_sig_posts BOOLEAN NOT NULL DEFAULT TRUE,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)


def downgrade() -> None:
    op.drop_table("user_preferences")
