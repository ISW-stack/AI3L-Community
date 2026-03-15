"""add on delete set null to posts category_id and post_reports reviewed_by

Revision ID: z7a8b9c0d1e2
Revises: y6z7a8b9c0d1
Create Date: 2026-03-15

"""

from alembic import op

revision = "z7a8b9c0d1e2"
down_revision = "y6z7a8b9c0d1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # posts.category_id → categories.id  ON DELETE SET NULL
    # The cascade migration y6z7a8b9c0d1 missed this FK.
    # Without SET NULL, deleting a category with posts causes a FK violation (500).
    op.drop_constraint("posts_category_id_fkey", "posts", type_="foreignkey")
    op.create_foreign_key(
        "posts_category_id_fkey",
        "posts",
        "categories",
        ["category_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # post_reports.reviewed_by → users.id  ON DELETE SET NULL
    # Also missed by the cascade migration. If a reviewer user is deleted,
    # the report should keep its data but clear the reviewer reference.
    op.drop_constraint("post_reports_reviewed_by_fkey", "post_reports", type_="foreignkey")
    op.create_foreign_key(
        "post_reports_reviewed_by_fkey",
        "post_reports",
        "users",
        ["reviewed_by"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    # Restore post_reports.reviewed_by → users.id  (no ON DELETE)
    op.drop_constraint("post_reports_reviewed_by_fkey", "post_reports", type_="foreignkey")
    op.create_foreign_key(
        "post_reports_reviewed_by_fkey",
        "post_reports",
        "users",
        ["reviewed_by"],
        ["id"],
    )

    # Restore posts.category_id → categories.id  (no ON DELETE)
    op.drop_constraint("posts_category_id_fkey", "posts", type_="foreignkey")
    op.create_foreign_key(
        "posts_category_id_fkey",
        "posts",
        "categories",
        ["category_id"],
        ["id"],
    )
