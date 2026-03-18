import datetime
import uuid

import sqlalchemy as sa
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, TSVECTOR, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Post(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "posts"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    category_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("categories.id"), nullable=True, index=True
    )
    sig_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sigs.id"), nullable=True, index=True
    )

    title: Mapped[str] = mapped_column(String(300), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    keywords: Mapped[list[str] | None] = mapped_column(ARRAY(String(50)), nullable=True)
    allow_comments: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=sa.text("true")
    )

    type: Mapped[str] = mapped_column(String(30), nullable=False, server_default=sa.text("'post'"))
    reactions: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    like_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=sa.text("0"))
    answer_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=sa.text("0"))
    best_answer_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default=sa.text("1"))
    comment_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=sa.text("0"))
    is_pinned: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=sa.text("false")
    )
    view_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=sa.text("0"))
    last_comment_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    is_deleted: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=sa.text("false")
    )

    search_vector: Mapped[str | None] = mapped_column(TSVECTOR, nullable=True)

    # Relationships
    author = relationship("User", lazy="selectin")
    category = relationship("Category", back_populates="posts", lazy="selectin")
    sig = relationship("Sig", lazy="selectin")
    comments = relationship("Comment", back_populates="post", lazy="noload")
    history = relationship("PostHistory", back_populates="post", lazy="noload")

    __table_args__ = (sa.Index("ix_posts_search_vector", "search_vector", postgresql_using="gin"),)
