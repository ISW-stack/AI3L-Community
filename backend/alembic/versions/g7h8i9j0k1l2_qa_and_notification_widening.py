"""Q&A post type and notification action_type widening

Revision ID: g7h8i9j0k1l2
Revises: f6g7h8i9j0k1
Create Date: 2026-03-15

"""

from alembic import op

revision = "g7h8i9j0k1l2"
down_revision = "f6g7h8i9j0k1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # posts: add type, best_answer_id, answer_count
    op.execute("ALTER TABLE posts ADD COLUMN type VARCHAR(30) NOT NULL DEFAULT 'post'")
    op.execute(
        "ALTER TABLE posts ADD CONSTRAINT chk_post_type " "CHECK (type IN ('post', 'question'))"
    )
    op.execute(
        "ALTER TABLE posts ADD COLUMN best_answer_id UUID "
        "REFERENCES comments(id) ON DELETE SET NULL"
    )
    op.execute("ALTER TABLE posts ADD COLUMN answer_count INTEGER NOT NULL DEFAULT 0")
    op.execute("CREATE INDEX ix_posts_type ON posts(type)")
    op.execute(
        "CREATE INDEX ix_posts_type_created_at ON posts(type, created_at DESC) "
        "WHERE is_deleted = false"
    )

    # comments: add is_best_answer, vote_score
    op.execute("ALTER TABLE comments ADD COLUMN is_best_answer " "BOOLEAN NOT NULL DEFAULT false")
    op.execute("ALTER TABLE comments ADD COLUMN vote_score INTEGER NOT NULL DEFAULT 0")
    op.execute(
        "CREATE INDEX ix_comments_post_id_vote_score "
        "ON comments(post_id, vote_score DESC) WHERE is_deleted = false"
    )

    # comment_votes
    op.execute("""
        CREATE TABLE comment_votes (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            comment_id UUID NOT NULL REFERENCES comments(id) ON DELETE CASCADE,
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            vote SMALLINT NOT NULL CHECK (vote IN (-1, 1)),
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT uq_comment_votes_comment_user UNIQUE (comment_id, user_id)
        )
    """)
    op.execute("CREATE INDEX ix_comment_votes_user ON comment_votes(user_id)")

    # Widen notifications action_type (audit fix H-03)
    op.execute("ALTER TABLE notifications ALTER COLUMN action_type TYPE VARCHAR(50)")


def downgrade() -> None:
    # Revert notifications action_type width
    op.execute("ALTER TABLE notifications ALTER COLUMN action_type TYPE VARCHAR(20)")

    # Drop comment_votes
    op.execute("DROP TABLE IF EXISTS comment_votes CASCADE")

    # Revert comments columns
    op.execute("DROP INDEX IF EXISTS ix_comments_post_id_vote_score")
    op.execute("ALTER TABLE comments DROP COLUMN IF EXISTS vote_score")
    op.execute("ALTER TABLE comments DROP COLUMN IF EXISTS is_best_answer")

    # Revert posts columns
    op.execute("DROP INDEX IF EXISTS ix_posts_type_created_at")
    op.execute("DROP INDEX IF EXISTS ix_posts_type")
    op.execute("ALTER TABLE posts DROP COLUMN IF EXISTS answer_count")
    op.execute("ALTER TABLE posts DROP COLUMN IF EXISTS best_answer_id")
    op.execute("ALTER TABLE posts DROP CONSTRAINT IF EXISTS chk_post_type")
    op.execute("ALTER TABLE posts DROP COLUMN IF EXISTS type")
