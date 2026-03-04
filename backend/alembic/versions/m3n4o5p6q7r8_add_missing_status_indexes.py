"""add missing status indexes for reports and applications

Revision ID: m3n4o5p6q7r8
Revises: l2m3n4o5p6q7
Create Date: 2026-03-04

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "m3n4o5p6q7r8"
down_revision: Union[str, None] = "l2m3n4o5p6q7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        "idx_post_reports_status",
        "post_reports",
        ["status"],
    )
    op.create_index(
        "idx_membership_applications_status",
        "membership_applications",
        ["status"],
    )
    op.create_index(
        "idx_membership_applications_user_status",
        "membership_applications",
        ["user_id", "status"],
    )
    op.create_index(
        "idx_post_reports_post_user_status",
        "post_reports",
        ["post_id", "user_id", "status"],
    )


def downgrade() -> None:
    op.drop_index("idx_post_reports_post_user_status", table_name="post_reports")
    op.drop_index("idx_membership_applications_user_status", table_name="membership_applications")
    op.drop_index("idx_membership_applications_status", table_name="membership_applications")
    op.drop_index("idx_post_reports_status", table_name="post_reports")
