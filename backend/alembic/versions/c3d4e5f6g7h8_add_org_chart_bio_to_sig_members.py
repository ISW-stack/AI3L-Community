"""add org_chart_bio to sig_members

Revision ID: c3d4e5f6g7h8
Revises: b2c3d4e5f6g7
Create Date: 2026-03-20

"""

import sqlalchemy as sa

from alembic import op

revision = "c3d4e5f6g7h8"
down_revision = "b2c3d4e5f6g7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "sig_members",
        sa.Column("org_chart_bio", sa.String(500), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("sig_members", "org_chart_bio")
