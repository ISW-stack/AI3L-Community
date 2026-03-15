"""add cascade rules and missing indexes

Revision ID: y6z7a8b9c0d1
Revises: x5y6z7a8b9c0
Create Date: 2026-03-15

"""

from alembic import op

revision = "y6z7a8b9c0d1"
down_revision = "x5y6z7a8b9c0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── FK CASCADE rules ─────────────────────────────────────────────
    # sig_members.sig_id → sigs.id  ON DELETE CASCADE
    op.drop_constraint("sig_members_sig_id_fkey", "sig_members", type_="foreignkey")
    op.create_foreign_key(
        "sig_members_sig_id_fkey",
        "sig_members",
        "sigs",
        ["sig_id"],
        ["id"],
        ondelete="CASCADE",
    )

    # sig_members.user_id → users.id  ON DELETE CASCADE
    op.drop_constraint("sig_members_user_id_fkey", "sig_members", type_="foreignkey")
    op.create_foreign_key(
        "sig_members_user_id_fkey",
        "sig_members",
        "users",
        ["user_id"],
        ["id"],
        ondelete="CASCADE",
    )

    # posts.sig_id → sigs.id  ON DELETE SET NULL
    op.drop_constraint("fk_posts_sig_id_sigs", "posts", type_="foreignkey")
    op.create_foreign_key(
        "fk_posts_sig_id_sigs",
        "posts",
        "sigs",
        ["sig_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # forms.sig_id → sigs.id  ON DELETE CASCADE
    op.drop_constraint("forms_sig_id_fkey", "forms", type_="foreignkey")
    op.create_foreign_key(
        "forms_sig_id_fkey",
        "forms",
        "sigs",
        ["sig_id"],
        ["id"],
        ondelete="CASCADE",
    )

    # form_responses.form_id → forms.id  ON DELETE CASCADE
    op.drop_constraint("form_responses_form_id_fkey", "form_responses", type_="foreignkey")
    op.create_foreign_key(
        "form_responses_form_id_fkey",
        "form_responses",
        "forms",
        ["form_id"],
        ["id"],
        ondelete="CASCADE",
    )

    # comments.post_id → posts.id  ON DELETE CASCADE
    op.drop_constraint("comments_post_id_fkey", "comments", type_="foreignkey")
    op.create_foreign_key(
        "comments_post_id_fkey",
        "comments",
        "posts",
        ["post_id"],
        ["id"],
        ondelete="CASCADE",
    )

    # post_history.post_id → posts.id  ON DELETE CASCADE
    op.drop_constraint("post_history_post_id_fkey", "post_history", type_="foreignkey")
    op.create_foreign_key(
        "post_history_post_id_fkey",
        "post_history",
        "posts",
        ["post_id"],
        ["id"],
        ondelete="CASCADE",
    )

    # post_reports.post_id → posts.id  ON DELETE CASCADE
    op.drop_constraint("post_reports_post_id_fkey", "post_reports", type_="foreignkey")
    op.create_foreign_key(
        "post_reports_post_id_fkey",
        "post_reports",
        "posts",
        ["post_id"],
        ["id"],
        ondelete="CASCADE",
    )

    # notifications.user_id → users.id  ON DELETE CASCADE
    op.drop_constraint("notifications_user_id_fkey", "notifications", type_="foreignkey")
    op.create_foreign_key(
        "notifications_user_id_fkey",
        "notifications",
        "users",
        ["user_id"],
        ["id"],
        ondelete="CASCADE",
    )

    # ── Missing indexes ──────────────────────────────────────────────
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_form_responses_user_id " "ON form_responses(user_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_comments_user_id_created "
        "ON comments(user_id, created_at DESC)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_post_reports_post_status "
        "ON post_reports(post_id, status)"
    )


def downgrade() -> None:
    # ── Drop new indexes ─────────────────────────────────────────────
    op.execute("DROP INDEX IF EXISTS idx_post_reports_post_status")
    op.execute("DROP INDEX IF EXISTS idx_comments_user_id_created")
    op.execute("DROP INDEX IF EXISTS idx_form_responses_user_id")

    # ── Restore FK constraints without CASCADE ───────────────────────
    # notifications.user_id → users.id  (no ON DELETE)
    op.drop_constraint("notifications_user_id_fkey", "notifications", type_="foreignkey")
    op.create_foreign_key(
        "notifications_user_id_fkey",
        "notifications",
        "users",
        ["user_id"],
        ["id"],
    )

    # post_reports.post_id → posts.id  (no ON DELETE)
    op.drop_constraint("post_reports_post_id_fkey", "post_reports", type_="foreignkey")
    op.create_foreign_key(
        "post_reports_post_id_fkey",
        "post_reports",
        "posts",
        ["post_id"],
        ["id"],
    )

    # post_history.post_id → posts.id  (no ON DELETE)
    op.drop_constraint("post_history_post_id_fkey", "post_history", type_="foreignkey")
    op.create_foreign_key(
        "post_history_post_id_fkey",
        "post_history",
        "posts",
        ["post_id"],
        ["id"],
    )

    # comments.post_id → posts.id  (no ON DELETE)
    op.drop_constraint("comments_post_id_fkey", "comments", type_="foreignkey")
    op.create_foreign_key(
        "comments_post_id_fkey",
        "comments",
        "posts",
        ["post_id"],
        ["id"],
    )

    # form_responses.form_id → forms.id  (no ON DELETE)
    op.drop_constraint("form_responses_form_id_fkey", "form_responses", type_="foreignkey")
    op.create_foreign_key(
        "form_responses_form_id_fkey",
        "form_responses",
        "forms",
        ["form_id"],
        ["id"],
    )

    # forms.sig_id → sigs.id  (no ON DELETE)
    op.drop_constraint("forms_sig_id_fkey", "forms", type_="foreignkey")
    op.create_foreign_key(
        "forms_sig_id_fkey",
        "forms",
        "sigs",
        ["sig_id"],
        ["id"],
    )

    # posts.sig_id → sigs.id  (no ON DELETE)
    op.drop_constraint("fk_posts_sig_id_sigs", "posts", type_="foreignkey")
    op.create_foreign_key(
        "fk_posts_sig_id_sigs",
        "posts",
        "sigs",
        ["sig_id"],
        ["id"],
    )

    # sig_members.user_id → users.id  (no ON DELETE)
    op.drop_constraint("sig_members_user_id_fkey", "sig_members", type_="foreignkey")
    op.create_foreign_key(
        "sig_members_user_id_fkey",
        "sig_members",
        "users",
        ["user_id"],
        ["id"],
    )

    # sig_members.sig_id → sigs.id  (no ON DELETE)
    op.drop_constraint("sig_members_sig_id_fkey", "sig_members", type_="foreignkey")
    op.create_foreign_key(
        "sig_members_sig_id_fkey",
        "sig_members",
        "sigs",
        ["sig_id"],
        ["id"],
    )
