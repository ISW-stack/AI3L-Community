"""add CHECK constraints on role/status enum columns

Revision ID: h09ck320002
Revises: h08fk320001
Create Date: 2026-03-21

"""

from alembic import op

revision = "h09ck320002"
down_revision = "h08fk320001"
branch_labels = None
depends_on = None

# (constraint_name, table, SQL expression)
_CHECKS = [
    (
        "ck_users_role",
        "users",
        "role IN ('SUPER_ADMIN', 'ADMIN', 'MEMBER', 'GUEST')",
    ),
    (
        "ck_membership_applications_status",
        "membership_applications",
        "status IN ('PENDING', 'APPROVED', 'REJECTED')",
    ),
    (
        "ck_post_reports_status",
        "post_reports",
        "status IN ('PENDING', 'RESOLVED', 'DISMISSED')",
    ),
    (
        "ck_sig_members_role",
        "sig_members",
        "role IN ('ADMIN', 'SUB_ADMIN', 'MEMBER')",
    ),
    (
        "ck_file_scans_status",
        "file_scans",
        "status IN ('pending', 'clean', 'malicious', 'unknown', 'error')",
    ),
]


def upgrade() -> None:
    for name, table, expr in _CHECKS:
        op.execute(f"ALTER TABLE {table} ADD CONSTRAINT {name} CHECK ({expr})")


def downgrade() -> None:
    for name, table, _ in reversed(_CHECKS):
        op.drop_constraint(name, table, type_="check")
