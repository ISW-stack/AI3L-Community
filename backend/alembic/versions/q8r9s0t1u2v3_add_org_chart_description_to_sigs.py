"""add org_chart_description to sigs

Revision ID: q8r9s0t1u2v3
Revises: p7q8r9s0t1u2
Create Date: 2026-03-20

"""

import sqlalchemy as sa

from alembic import op

revision = "q8r9s0t1u2v3"
down_revision = "p7q8r9s0t1u2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "sigs",
        sa.Column("org_chart_description", sa.String(1000), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("sigs", "org_chart_description")
