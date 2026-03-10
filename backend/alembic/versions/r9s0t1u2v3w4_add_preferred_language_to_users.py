"""add preferred_language to users

Revision ID: r9s0t1u2v3w4
Revises: q7r8s9t0u1v2
Create Date: 2026-03-08 00:00:00.000000

"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "r9s0t1u2v3w4"
down_revision = "q7r8s9t0u1v2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "preferred_language",
            sa.String(10),
            nullable=False,
            server_default="en",
        ),
    )


def downgrade() -> None:
    op.drop_column("users", "preferred_language")
