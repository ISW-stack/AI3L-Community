"""views and citations — profile views, post citations, counters

Revision ID: e5f6g7h8i9j0
Revises: d4e5f6g7h8i9
Create Date: 2026-03-15

"""

from alembic import op

revision = "e5f6g7h8i9j0"
down_revision = "d4e5f6g7h8i9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # profile_views
    op.execute("""
        CREATE TABLE profile_views (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            profile_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            viewer_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            view_count INTEGER NOT NULL DEFAULT 1,
            first_viewed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            last_viewed_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    op.execute(
        "CREATE UNIQUE INDEX idx_profile_views_unique "
        "ON profile_views (profile_id, viewer_id)"
    )

    # user profile view counters
    op.execute(
        "ALTER TABLE users ADD COLUMN profile_view_count_unique "
        "INTEGER NOT NULL DEFAULT 0"
    )
    op.execute(
        "ALTER TABLE users ADD COLUMN profile_view_count_total "
        "INTEGER NOT NULL DEFAULT 0"
    )

    # post_citations
    op.execute("""
        CREATE TABLE post_citations (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            citing_post_id UUID NOT NULL REFERENCES posts(id) ON DELETE CASCADE,
            cited_post_id UUID NOT NULL REFERENCES posts(id) ON DELETE CASCADE,
            is_self_citation BOOLEAN NOT NULL DEFAULT false,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    op.execute(
        "CREATE UNIQUE INDEX idx_post_citations_unique "
        "ON post_citations (citing_post_id, cited_post_id)"
    )
    op.execute(
        "CREATE INDEX idx_post_citations_cited ON post_citations (cited_post_id)"
    )

    # post citation counter
    op.execute(
        "ALTER TABLE posts ADD COLUMN citation_count INTEGER NOT NULL DEFAULT 0"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE posts DROP COLUMN IF EXISTS citation_count")
    op.execute("DROP TABLE IF EXISTS post_citations CASCADE")
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS profile_view_count_total")
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS profile_view_count_unique")
    op.execute("DROP TABLE IF EXISTS profile_views CASCADE")
