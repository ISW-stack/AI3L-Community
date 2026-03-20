"""add org_chart_description to sigs

Revision ID: d4e5f6g7h8i9
Revises: c3d4e5f6g7h8
Create Date: 2026-03-20

"""

import sqlalchemy as sa

from alembic import op

revision = "d4e5f6g7h8i9"
down_revision = "c3d4e5f6g7h8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "sigs",
        sa.Column("org_chart_description", sa.String(1000), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("sigs", "org_chart_description")
