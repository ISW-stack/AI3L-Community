"""remove unused sub_admin_ids column from categories

Revision ID: i9j0k1l2m3n4
Revises: h8i9j0k1l2m3
Create Date: 2026-03-02 12:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "i9j0k1l2m3n4"
down_revision: Union[str, None] = "h8i9j0k1l2m3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_column("categories", "sub_admin_ids")


def downgrade() -> None:
    op.add_column(
        "categories",
        sa.Column("sub_admin_ids", postgresql.ARRAY(sa.UUID()), nullable=True),
    )
