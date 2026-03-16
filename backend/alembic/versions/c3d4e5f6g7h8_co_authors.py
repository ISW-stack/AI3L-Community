"""co-authors — post co-author table

Revision ID: c3d4e5f6g7h8
Revises: b2c3d4e5f6g7
Create Date: 2026-03-15

"""

from alembic import op

revision = "c3d4e5f6g7h8"
down_revision = "b2c3d4e5f6g7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE post_co_authors (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            post_id UUID NOT NULL REFERENCES posts(id) ON DELETE CASCADE,
            user_id UUID REFERENCES users(id) ON DELETE SET NULL,
            display_name VARCHAR(100) NOT NULL,
            affiliation VARCHAR(200),
            orcid VARCHAR(30),
            is_external BOOLEAN NOT NULL DEFAULT FALSE,
            status VARCHAR(10) NOT NULL DEFAULT 'PENDING'
                CHECK (status IN ('PENDING', 'ACCEPTED', 'REJECTED')),
            invited_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            responded_at TIMESTAMPTZ,
            invited_by UUID REFERENCES users(id) ON DELETE SET NULL,
            CONSTRAINT uq_post_co_author UNIQUE (post_id, user_id),
            CONSTRAINT chk_internal_user
                CHECK ((is_external = TRUE) OR (user_id IS NOT NULL))
        )
    """)
    op.execute("CREATE INDEX ix_post_co_authors_post_id ON post_co_authors(post_id)")
    op.execute(
        "CREATE INDEX ix_post_co_authors_user_id ON post_co_authors(user_id) "
        "WHERE user_id IS NOT NULL"
    )
    op.execute("CREATE INDEX ix_post_co_authors_status ON post_co_authors(post_id, status)")
    # Partial unique index for external co-authors (audit fix C-09)
    op.execute(
        "CREATE UNIQUE INDEX ix_post_co_author_external "
        "ON post_co_authors (post_id, display_name, COALESCE(affiliation, '')) "
        "WHERE is_external = TRUE"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS post_co_authors CASCADE")
