"""add allow_guests to forms

Revision ID: b1c2d3e4f5g6
Revises: merge320005
Create Date: 2026-03-31

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b1c2d3e4f5g6"
down_revision: Union[str, None] = "merge320005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add the new column with default false
    op.add_column(
        "forms",
        sa.Column(
            "allow_guests",
            sa.Boolean,
            server_default=sa.text("false"),
            nullable=False,
        ),
    )

    # 2. Backward compatibility: standalone forms previously allowed guests
    op.execute("UPDATE forms SET allow_guests = true WHERE sig_id IS NULL")

    # 3. Backward compatibility: SIG forms with allow_non_members=true also allowed guests
    op.execute(
        "UPDATE forms SET allow_guests = true "
        "WHERE sig_id IS NOT NULL AND allow_non_members = true"
    )


def downgrade() -> None:
    op.drop_column("forms", "allow_guests")
