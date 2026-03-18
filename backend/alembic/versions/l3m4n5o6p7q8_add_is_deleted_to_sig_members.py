"""add is_deleted to sig_members

Revision ID: l3m4n5o6p7q8
Revises: b2c3d4e5f6g8
Create Date: 2026-03-18 12:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "l3m4n5o6p7q8"
down_revision: Union[str, None] = "b2c3d4e5f6g8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "sig_members",
        sa.Column(
            "is_deleted",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.create_index("ix_sig_members_is_deleted", "sig_members", ["is_deleted"])


def downgrade() -> None:
    op.drop_index("ix_sig_members_is_deleted", table_name="sig_members")
    op.drop_column("sig_members", "is_deleted")
