"""add case-insensitive unique index on categories.name

Revision ID: a1b2c3d4e5f6
Revises: z7a8b9c0d1e2
Create Date: 2026-03-17

"""

from alembic import op

revision = "a1b2c3d4e5f6"
down_revision = "z7a8b9c0d1e2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_categories_name ON categories (LOWER(name))"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_categories_name")
