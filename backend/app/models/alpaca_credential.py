"""Per-user Alpaca API credentials (secret stored encrypted)."""
from __future__ import annotations

from uuid import UUID

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, new_uuid


class AlpacaCredential(Base, TimestampMixin):
    __tablename__ = "alpaca_credentials"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_uuid)
    # One credential per user.
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True, index=True
    )
    api_key: Mapped[str] = mapped_column(String(64))
    secret_encrypted: Mapped[str] = mapped_column(Text)
