"""add events table and event_id to comments

Revision ID: a8b9c0d1e2f3
Revises: z7a8b9c0d1e2
Create Date: 2026-03-31

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import ARRAY, UUID

revision = "a8b9c0d1e2f3"
down_revision = "z7a8b9c0d1e2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "events",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("sig_id", UUID(as_uuid=True), sa.ForeignKey("sigs.id", ondelete="SET NULL"), nullable=True),
        sa.Column("visibility", ARRAY(sa.Text()), nullable=False),
        sa.Column("allow_comments", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("comment_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("reactions", sa.Text(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
    )

    op.create_index(
        "ix_events_created_at",
        "events",
        ["created_at"],
        unique=False,
        postgresql_where=sa.text("is_deleted = false"),
    )
    op.create_index(
        "ix_events_sig_id",
        "events",
        ["sig_id"],
        unique=False,
        postgresql_where=sa.text("is_deleted = false AND sig_id IS NOT NULL"),
    )
    op.create_index(
        "ix_events_visibility",
        "events",
        ["visibility"],
        unique=False,
        postgresql_using="gin",
    )

    # Make comments.post_id nullable (was NOT NULL)
    op.alter_column("comments", "post_id", existing_type=UUID(as_uuid=True), nullable=True)

    # Add event_id to comments
    op.add_column("comments", sa.Column("event_id", UUID(as_uuid=True), nullable=True))
    op.create_foreign_key(
        "comments_event_id_fkey",
        "comments",
        "events",
        ["event_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index("ix_comments_event_id", "comments", ["event_id"], postgresql_where=sa.text("event_id IS NOT NULL"))

    # Ensure exactly one of post_id or event_id is set
    op.execute(
        "ALTER TABLE comments ADD CONSTRAINT chk_comment_target "
        "CHECK (num_nonnulls(post_id, event_id) = 1)"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE comments DROP CONSTRAINT IF EXISTS chk_comment_target")
    op.drop_index("ix_comments_event_id", "comments")
    op.drop_constraint("comments_event_id_fkey", "comments", type_="foreignkey")
    op.drop_column("comments", "event_id")
    # Restore post_id NOT NULL (backfill first if needed)
    op.alter_column("comments", "post_id", existing_type=UUID(as_uuid=True), nullable=False)

    op.drop_index("ix_events_visibility", "events")
    op.drop_index("ix_events_sig_id", "events")
    op.drop_index("ix_events_created_at", "events")
    op.drop_table("events")
