"""clear existing form descriptions for rich-text migration

Revision ID: t1u2v3w4x5y6
Revises: s0t1u2v3w4x5
Create Date: 2026-03-11

Form descriptions will now be stored as sanitized HTML (rendered via v-html).
Existing plain-text descriptions are cleared during this migration since the
project is still in active development and has no production data to preserve.
"""

from alembic import op

revision = "t1u2v3w4x5y6"
down_revision = "s0t1u2v3w4x5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("UPDATE forms SET description = NULL WHERE description IS NOT NULL")


def downgrade() -> None:
    # Cannot restore cleared descriptions
    pass
