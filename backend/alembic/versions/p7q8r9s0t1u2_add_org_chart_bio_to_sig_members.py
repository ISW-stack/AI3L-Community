"""add org_chart_bio to sig_members

Revision ID: p7q8r9s0t1u2
Revises: o6p7q8r9s0t1
Create Date: 2026-03-20

"""

import sqlalchemy as sa

from alembic import op

revision = "p7q8r9s0t1u2"
down_revision = "o6p7q8r9s0t1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "sig_members",
        sa.Column("org_chart_bio", sa.String(500), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("sig_members", "org_chart_bio")
