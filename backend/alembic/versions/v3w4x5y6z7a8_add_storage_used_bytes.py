"""add storage_used_bytes to users

Revision ID: v3w4x5y6z7a8
Revises: u2v3w4x5y6z7
Create Date: 2026-03-11

"""

import sqlalchemy as sa

from alembic import op

revision = "v3w4x5y6z7a8"
down_revision = "u2v3w4x5y6z7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("storage_used_bytes", sa.BigInteger(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_column("users", "storage_used_bytes")
