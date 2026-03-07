"""fix sig name unique constraint to exclude soft-deleted rows

Revision ID: o5p6q7r8s9t0
Revises: n4o5p6q7r8s9
Create Date: 2026-03-06 12:00:00.000000

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "o5p6q7r8s9t0"
down_revision: Union[str, None] = "n4o5p6q7r8s9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Drop the old unconditional unique constraint on sigs.name
    op.drop_constraint("sigs_name_key", "sigs", type_="unique")
    # Create a partial unique index that only applies to active (non-deleted) SIGs
    op.execute("CREATE UNIQUE INDEX uq_sigs_name_active ON sigs (name) WHERE is_deleted = false")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_sigs_name_active")
    op.create_unique_constraint("sigs_name_key", "sigs", ["name"])
