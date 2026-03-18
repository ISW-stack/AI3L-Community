"""add ip_bans table

Revision ID: b2c3d4e5f6g8
Revises: a1b2c3d4e5f6
Create Date: 2026-03-18
"""
import sqlalchemy as sa
from alembic import op

revision = "b2c3d4e5f6g8"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ip_bans",
        sa.Column(
            "id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            primary_key=True,
        ),
        sa.Column("ip_address", sa.String(45), nullable=False),
        sa.Column("reason", sa.Text, nullable=False, server_default=""),
        sa.Column(
            "banned_by",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_ip_bans_ip_address", "ip_bans", ["ip_address"])


def downgrade() -> None:
    op.drop_index("ix_ip_bans_ip_address")
    op.drop_table("ip_bans")
