"""phase3_sigs_sig_members_post_reports

Revision ID: c3f8a1b2d4e5
Revises: 83ded9c22efe
Create Date: 2026-02-28 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'c3f8a1b2d4e5'
down_revision: Union[str, None] = '83ded9c22efe'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- sigs table ---
    op.create_table('sigs',
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('created_by', sa.UUID(), nullable=False),
        sa.Column('is_deleted', sa.Boolean(), server_default=sa.text('false'), nullable=False),
        sa.Column('member_count', sa.Integer(), server_default=sa.text('0'), nullable=False),
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['created_by'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name'),
    )

    # --- sig_members table ---
    op.create_table('sig_members',
        sa.Column('sig_id', sa.UUID(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('role', sa.String(length=20), server_default=sa.text("'MEMBER'"), nullable=False),
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['sig_id'], ['sigs.id']),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('sig_id', 'user_id', name='uq_sig_members_sig_user'),
    )
    op.create_index(op.f('ix_sig_members_sig_id'), 'sig_members', ['sig_id'], unique=False)
    op.create_index(op.f('ix_sig_members_user_id'), 'sig_members', ['user_id'], unique=False)

    # --- post_reports table ---
    op.create_table('post_reports',
        sa.Column('post_id', sa.UUID(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('reason', sa.Text(), nullable=False),
        sa.Column('status', sa.String(length=20), server_default=sa.text("'PENDING'"), nullable=False),
        sa.Column('reviewed_by', sa.UUID(), nullable=True),
        sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['post_id'], ['posts.id']),
        sa.ForeignKeyConstraint(['reviewed_by'], ['users.id']),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_post_reports_post_id'), 'post_reports', ['post_id'], unique=False)
    op.create_index(op.f('ix_post_reports_user_id'), 'post_reports', ['user_id'], unique=False)

    # --- Add FK constraint on posts.sig_id -> sigs.id (column already exists) ---
    op.create_foreign_key('fk_posts_sig_id_sigs', 'posts', 'sigs', ['sig_id'], ['id'])


def downgrade() -> None:
    op.drop_constraint('fk_posts_sig_id_sigs', 'posts', type_='foreignkey')

    op.drop_index(op.f('ix_post_reports_user_id'), table_name='post_reports')
    op.drop_index(op.f('ix_post_reports_post_id'), table_name='post_reports')
    op.drop_table('post_reports')

    op.drop_index(op.f('ix_sig_members_user_id'), table_name='sig_members')
    op.drop_index(op.f('ix_sig_members_sig_id'), table_name='sig_members')
    op.drop_table('sig_members')

    op.drop_table('sigs')
