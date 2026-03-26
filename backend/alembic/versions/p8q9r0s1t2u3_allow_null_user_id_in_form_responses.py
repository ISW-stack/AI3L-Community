"""allow null user_id in form_responses for guest submissions

Revision ID: p8q9r0s1t2u3
Revises: o7p8q9r0s1t2
Create Date: 2026-03-26 10:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "p8q9r0s1t2u3"
down_revision: Union[str, None] = "o7p8q9r0s1t2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Make user_id nullable for guest form submissions
    op.alter_column("form_responses", "user_id", existing_type=sa.UUID(), nullable=True)

    # Drop old unique constraint that requires user_id NOT NULL for uniqueness
    op.drop_constraint("uq_form_responses_form_user", "form_responses", type_="unique")

    # Create a partial unique index only for rows with non-null user_id
    # (guests can submit multiple times, rate-limited by IP at endpoint level)
    op.create_index(
        "uq_form_responses_form_user",
        "form_responses",
        ["form_id", "user_id"],
        unique=True,
        postgresql_where=sa.text("user_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_form_responses_form_user", table_name="form_responses")
    op.create_unique_constraint(
        "uq_form_responses_form_user", "form_responses", ["form_id", "user_id"]
    )
    op.alter_column("form_responses", "user_id", existing_type=sa.UUID(), nullable=False)
