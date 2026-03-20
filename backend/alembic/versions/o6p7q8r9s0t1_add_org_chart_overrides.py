"""add org_chart_overrides table

Revision ID: o6p7q8r9s0t1
Revises: n5o6p7q8r9s0
Create Date: 2026-03-20

"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "o6p7q8r9s0t1"
down_revision = "n5o6p7q8r9s0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "org_chart_overrides",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("entity_type", sa.String(20), nullable=False),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("custom_title", sa.String(200), nullable=True),
        sa.Column("custom_description", sa.Text(), nullable=True),
        sa.Column("display_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_visible", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("updated_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.ForeignKeyConstraint(["updated_by"], ["users.id"]),
        sa.UniqueConstraint("entity_type", "entity_id", name="uq_org_chart_overrides_entity"),
    )


def downgrade() -> None:
    op.drop_table("org_chart_overrides")
