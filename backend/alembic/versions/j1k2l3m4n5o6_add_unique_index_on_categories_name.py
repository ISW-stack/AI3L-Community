"""add case-insensitive unique index on categories.name

Revision ID: j1k2l3m4n5o6
Revises: i9k0l1m2n3o4
Create Date: 2026-03-17

"""

from alembic import op

revision = "j1k2l3m4n5o6"
down_revision = "i9k0l1m2n3o4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE UNIQUE INDEX IF NOT EXISTS uq_categories_name ON categories (LOWER(name))")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_categories_name")
