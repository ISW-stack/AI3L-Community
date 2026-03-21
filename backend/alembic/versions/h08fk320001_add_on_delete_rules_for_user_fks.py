"""add ON DELETE rules for remaining user FK constraints

Revision ID: h08fk320001
Revises: q8r9s0t1u2v3
Create Date: 2026-03-21

"""

from alembic import op

revision = "h08fk320001"
down_revision = "q8r9s0t1u2v3"
branch_labels = None
depends_on = None

# FK updates: (table, column, constraint_name, on_delete, needs_nullable)
_SET_NULL_FKS = [
    ("posts", "user_id", "posts_user_id_fkey", True),
    ("comments", "user_id", "comments_user_id_fkey", True),
    ("audit_logs", "user_id", "audit_logs_user_id_fkey", True),
    ("notifications", "trigger_user_id", "notifications_trigger_user_id_fkey", False),
    ("invite_codes", "created_by", "invite_codes_created_by_fkey", True),
    ("invite_codes", "consumed_by", "invite_codes_consumed_by_fkey", False),
    ("membership_applications", "reviewed_by", "membership_applications_reviewed_by_fkey", False),
    ("forms", "created_by", "forms_created_by_fkey", True),
    ("form_responses", "user_id", "form_responses_user_id_fkey", True),
    ("post_reports", "user_id", "post_reports_user_id_fkey", True),
    ("sigs", "created_by", "sigs_created_by_fkey", True),
]

_CASCADE_FKS = [
    ("privacy_consents", "user_id", "privacy_consents_user_id_fkey"),
    ("membership_applications", "user_id", "membership_applications_user_id_fkey"),
]


def upgrade() -> None:
    # ── SET NULL FKs ──────────────────────────────────────────────────
    for table, column, constraint, needs_nullable in _SET_NULL_FKS:
        if needs_nullable:
            op.alter_column(table, column, nullable=True)
        op.drop_constraint(constraint, table, type_="foreignkey")
        op.create_foreign_key(
            constraint, table, "users", [column], ["id"], ondelete="SET NULL"
        )

    # ── CASCADE FKs ───────────────────────────────────────────────────
    for table, column, constraint in _CASCADE_FKS:
        op.drop_constraint(constraint, table, type_="foreignkey")
        op.create_foreign_key(
            constraint, table, "users", [column], ["id"], ondelete="CASCADE"
        )


def downgrade() -> None:
    # ── Restore CASCADE FKs without ON DELETE ─────────────────────────
    for table, column, constraint in reversed(_CASCADE_FKS):
        op.drop_constraint(constraint, table, type_="foreignkey")
        op.create_foreign_key(constraint, table, "users", [column], ["id"])

    # ── Restore SET NULL FKs without ON DELETE ────────────────────────
    for table, column, constraint, needs_nullable in reversed(_SET_NULL_FKS):
        op.drop_constraint(constraint, table, type_="foreignkey")
        op.create_foreign_key(constraint, table, "users", [column], ["id"])
        if needs_nullable:
            op.alter_column(table, column, nullable=False)
