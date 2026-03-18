"""merge dm and sig_members branches

Revision ID: m4n5o6p7q8r9
Revises: k2l3m4n5o6p7, l3m4n5o6p7q8
Create Date: 2026-03-18

"""

from typing import Sequence, Union

revision: str = "m4n5o6p7q8r9"
down_revision: Union[str, Sequence[str], None] = ("k2l3m4n5o6p7", "l3m4n5o6p7q8")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
