"""add is_closed to forms

Revision ID: i9k0l1m2n3o4
Revises: h8j9k0l1m2n3
Create Date: 2026-03-16

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "i9k0l1m2n3o4"
down_revision: Union[str, None] = "h8j9k0l1m2n3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "forms",
        sa.Column(
            "is_closed",
            sa.Boolean,
            server_default=sa.text("false"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("forms", "is_closed")
