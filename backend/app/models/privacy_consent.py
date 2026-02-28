import uuid

from sqlalchemy import ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class PrivacyConsent(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "privacy_consents"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    ip_address: Mapped[str] = mapped_column(String(45), nullable=False)

    user = relationship("User", lazy="selectin")
