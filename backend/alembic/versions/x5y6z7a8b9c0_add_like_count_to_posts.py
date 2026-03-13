"""add like_count to posts

Revision ID: x5y6z7a8b9c0
Revises: w4x5y6z7a8b9
Create Date: 2026-03-13

"""

import sqlalchemy as sa

from alembic import op

revision = "x5y6z7a8b9c0"
down_revision = "w4x5y6z7a8b9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "posts",
        sa.Column(
            "like_count",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )
    # Backfill like_count from existing reactions JSONB
    op.execute("""
        UPDATE posts
        SET like_count = COALESCE(
            jsonb_array_length(reactions->'like'), 0
        )
        WHERE reactions IS NOT NULL
          AND reactions ? 'like'
    """)
    # Index for popular sort
    op.create_index("idx_posts_like_count", "posts", [sa.text("like_count DESC")])


def downgrade() -> None:
    op.drop_index("idx_posts_like_count", table_name="posts")
    op.drop_column("posts", "like_count")
