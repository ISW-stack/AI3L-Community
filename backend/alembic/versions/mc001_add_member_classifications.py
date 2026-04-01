"""Add member_classifications table.

Stores the manual category assignment for each user on the About > Members page.
Categories: chair, co_chair, ec_member, sig_chair, sre, member.
Each user can only appear in one category (UNIQUE on user_id).

Revision ID: mc001
Revises: merge320005
Create Date: 2026-04-01
"""

import sqlalchemy as sa

from alembic import op

revision = "mc001"
down_revision = "b1c2d3e4f5g6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "member_classifications",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("category", sa.VARCHAR(30), nullable=False),
        sa.Column("display_order", sa.Integer, nullable=False, server_default="0"),
        sa.Column(
            "assigned_by",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index(
        "ix_member_classifications_category",
        "member_classifications",
        ["category", "display_order"],
    )


def downgrade() -> None:
    op.drop_index("ix_member_classifications_category")
    op.drop_table("member_classifications")
