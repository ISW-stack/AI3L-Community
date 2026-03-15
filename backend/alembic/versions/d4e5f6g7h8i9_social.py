"""social — friendships, follows, blocks

Revision ID: d4e5f6g7h8i9
Revises: c3d4e5f6g7h8
Create Date: 2026-03-15

"""

from alembic import op

revision = "d4e5f6g7h8i9"
down_revision = "c3d4e5f6g7h8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # friendships
    op.execute("""
        CREATE TABLE friendships (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            requester_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            addressee_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            status VARCHAR(10) NOT NULL DEFAULT 'PENDING'
                CHECK (status IN ('PENDING', 'ACCEPTED')),
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT uq_friendship UNIQUE (requester_id, addressee_id),
            CONSTRAINT ck_friendship_self CHECK (requester_id != addressee_id)
        )
    """)
    # Bidirectional unique index (audit fix C-06)
    op.execute(
        "CREATE UNIQUE INDEX ix_friendships_pair ON friendships "
        "(LEAST(requester_id, addressee_id), GREATEST(requester_id, addressee_id))"
    )
    op.execute(
        "CREATE INDEX ix_friendships_requester ON friendships(requester_id, status)"
    )
    op.execute(
        "CREATE INDEX ix_friendships_addressee ON friendships(addressee_id, status)"
    )

    # follows
    op.execute("""
        CREATE TABLE follows (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            follower_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            following_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT uq_follow UNIQUE (follower_id, following_id),
            CONSTRAINT ck_follow_self CHECK (follower_id != following_id)
        )
    """)
    op.execute("CREATE INDEX ix_follows_follower ON follows(follower_id)")
    op.execute("CREATE INDEX ix_follows_following ON follows(following_id)")

    # blocks
    op.execute("""
        CREATE TABLE blocks (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            blocker_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            blocked_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT uq_block UNIQUE (blocker_id, blocked_id),
            CONSTRAINT ck_block_self CHECK (blocker_id != blocked_id)
        )
    """)
    op.execute("CREATE INDEX ix_blocks_blocker ON blocks(blocker_id)")
    op.execute("CREATE INDEX ix_blocks_blocked ON blocks(blocked_id)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS blocks CASCADE")
    op.execute("DROP TABLE IF EXISTS follows CASCADE")
    op.execute("DROP TABLE IF EXISTS friendships CASCADE")
