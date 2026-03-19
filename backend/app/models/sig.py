import uuid

import sqlalchemy as sa
from sqlalchemy import Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Sig(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "sigs"

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    # Uniqueness for active SIGs enforced via partial index
    # uq_sigs_name_active (migration o5p6q7r8s9t0)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    is_deleted: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=sa.text("false")
    )
    member_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=sa.text("0"))


class SigMember(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "sig_members"

    sig_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sigs.id"), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default=sa.text("'MEMBER'")
    )
    is_deleted: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=sa.text("false")
    )

    __table_args__ = (sa.UniqueConstraint("sig_id", "user_id", name="uq_sig_members_sig_user"),)
