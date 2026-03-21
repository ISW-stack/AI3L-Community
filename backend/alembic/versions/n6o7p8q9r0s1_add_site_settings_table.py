"""add site_settings table

Revision ID: n6o7p8q9r0s1
Revises: merge320004
Create Date: 2026-03-22
"""

import sqlalchemy as sa

from alembic import op

revision = "n6o7p8q9r0s1"
down_revision = "merge320004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "site_settings",
        sa.Column("key", sa.VARCHAR(100), primary_key=True),
        sa.Column("value", sa.Text, nullable=False, server_default=""),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    # Seed default values
    op.execute(
        sa.text(
            "INSERT INTO site_settings (key, value) VALUES "
            "('about_intro_photo', ''), "
            "('about_intro_bio', '')"
        )
    )


def downgrade() -> None:
    op.drop_table("site_settings")
