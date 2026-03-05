"""add contributors table

Revision ID: n4o5p6q7r8s9
Revises: m3n4o5p6q7r8
Create Date: 2026-03-05
"""

import sqlalchemy as sa

from alembic import op

revision = "n4o5p6q7r8s9"
down_revision = "m3n4o5p6q7r8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "contributors",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("github_username", sa.VARCHAR(100), nullable=False, unique=True),
        sa.Column("display_name", sa.VARCHAR(100), nullable=False),
        sa.Column("role", sa.VARCHAR(200), nullable=False),
        sa.Column("display_order", sa.Integer, nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    # Seed initial contributors (hardcoded UUIDs for deterministic migration)
    op.execute(
        sa.text(
            "INSERT INTO contributors"
            " (id, github_username, display_name, role, display_order)"
            " VALUES ('a1b2c3d4-e5f6-7890-abcd-ef1234567890',"
            " 'Isaries', 'Isaries', 'Project Lead & Full-Stack Developer', 0)"
        )
    )
    op.execute(
        sa.text(
            "INSERT INTO contributors"
            " (id, github_username, display_name, role, display_order)"
            " VALUES ('b2c3d4e5-f6a7-8901-bcde-f12345678901',"
            " 'SW9526', 'SW9526', 'Frontend Contributor', 1)"
        )
    )


def downgrade() -> None:
    op.drop_table("contributors")
