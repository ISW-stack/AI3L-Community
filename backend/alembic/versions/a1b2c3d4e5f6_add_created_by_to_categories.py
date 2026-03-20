"""add created_by to categories

Revision ID: a1b2c3d4e5f6
Revises: z7a8b9c0d1e2
Create Date: 2026-03-20

"""

import sqlalchemy as sa

from alembic import op

revision = "a1b2c3d4e5f6"
down_revision = "z7a8b9c0d1e2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "categories",
        sa.Column("created_by", sa.dialects.postgresql.UUID(), nullable=True),
    )
    op.create_foreign_key(
        "fk_categories_created_by_users",
        "categories",
        "users",
        ["created_by"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_categories_created_by_users", "categories", type_="foreignkey")
    op.drop_column("categories", "created_by")
