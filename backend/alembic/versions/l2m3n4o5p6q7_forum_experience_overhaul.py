"""forum experience overhaul

Revision ID: l2m3n4o5p6q7
Revises: k1l2m3n4o5p6
Create Date: 2026-03-03

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "l2m3n4o5p6q7"
down_revision: Union[str, None] = "k1l2m3n4o5p6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "posts",
        sa.Column(
            "is_pinned",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.add_column(
        "posts",
        sa.Column(
            "view_count",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )
    op.add_column(
        "posts",
        sa.Column(
            "last_comment_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )

    # Backfill last_comment_at from existing comments
    op.execute("""
        UPDATE posts SET last_comment_at = (
            SELECT MAX(c.created_at)
            FROM comments c
            WHERE c.post_id = posts.id AND c.is_deleted = false
        )
        """)

    # Partial index for pinned posts
    op.create_index(
        "idx_posts_is_pinned",
        "posts",
        ["is_pinned"],
        postgresql_where=sa.text("is_pinned = true AND is_deleted = false"),
    )
    op.create_index(
        "idx_posts_last_comment_at",
        "posts",
        [sa.text("last_comment_at DESC NULLS LAST")],
    )


def downgrade() -> None:
    op.drop_index("idx_posts_last_comment_at", table_name="posts")
    op.drop_index("idx_posts_is_pinned", table_name="posts")
    op.drop_column("posts", "last_comment_at")
    op.drop_column("posts", "view_count")
    op.drop_column("posts", "is_pinned")
