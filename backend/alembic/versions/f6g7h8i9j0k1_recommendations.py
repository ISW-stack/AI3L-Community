"""recommendations — friend recommendation tables

Revision ID: f6g7h8i9j0k1
Revises: e5f6g7h8i9j0
Create Date: 2026-03-15

"""

from alembic import op

revision = "f6g7h8i9j0k1"
down_revision = "e5f6g7h8i9j0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # friend_recommendations
    op.execute("""
        CREATE TABLE friend_recommendations (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            recommended_user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            score REAL NOT NULL DEFAULT 0.0,
            reasons JSONB NOT NULL DEFAULT '[]',
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT uq_friend_rec_user_pair
                UNIQUE (user_id, recommended_user_id),
            CONSTRAINT ck_friend_rec_no_self
                CHECK (user_id <> recommended_user_id)
        )
    """)
    op.execute(
        "CREATE INDEX ix_friend_rec_user_score " "ON friend_recommendations (user_id, score DESC)"
    )

    # dismissed_recommendations
    op.execute("""
        CREATE TABLE dismissed_recommendations (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            dismissed_user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT uq_dismissed_pair UNIQUE (user_id, dismissed_user_id)
        )
    """)
    op.execute("CREATE INDEX ix_dismissed_user ON dismissed_recommendations (user_id)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS dismissed_recommendations CASCADE")
    op.execute("DROP TABLE IF EXISTS friend_recommendations CASCADE")
