"""SQLAlchemy declarative base and shared column mixins.

All ORM models inherit from `Base`. `TimestampMixin` provides the
`created_at`/`updated_at` columns the data model requires on every table.
Importing `app.models` registers every model on `Base.metadata`, which is what
Alembic autogenerate targets.
"""
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


def new_uuid() -> UUID:
    """Default factory for UUID primary keys."""
    return uuid4()
