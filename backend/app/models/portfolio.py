"""Portfolio, Position, and Trade ORM models (docs/04-data-model.md)."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, new_uuid


class Portfolio(Base, TimestampMixin):
    __tablename__ = "portfolios"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_uuid)
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(120))
    # "simulated" (internal engine) or "alpaca" (mirrors the Alpaca paper account).
    broker: Mapped[str] = mapped_column(String(16), default="simulated")
    starting_cash: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    cash_balance: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    alpaca_account_id: Mapped[str | None] = mapped_column(String(64), nullable=True)

    positions: Mapped[list[Position]] = relationship(
        back_populates="portfolio", cascade="all, delete-orphan", order_by="Position.symbol"
    )
    trades: Mapped[list[Trade]] = relationship(
        back_populates="portfolio", cascade="all, delete-orphan",
        order_by="Trade.executed_at",
    )


class Position(Base, TimestampMixin):
    __tablename__ = "positions"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_uuid)
    portfolio_id: Mapped[UUID] = mapped_column(
        ForeignKey("portfolios.id", ondelete="CASCADE"), index=True
    )
    symbol: Mapped[str] = mapped_column(String(32), index=True)
    asset_type: Mapped[str] = mapped_column(String(16), default="stock")
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 4))
    avg_cost: Mapped[Decimal] = mapped_column(Numeric(18, 4))
    current_price: Mapped[Decimal] = mapped_column(Numeric(18, 4))
    unrealized_pl: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0"))
    opened_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    portfolio: Mapped[Portfolio] = relationship(back_populates="positions")


class Trade(Base, TimestampMixin):
    __tablename__ = "trades"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_uuid)
    portfolio_id: Mapped[UUID] = mapped_column(
        ForeignKey("portfolios.id", ondelete="CASCADE"), index=True
    )
    # Source recommendation, if accepted from research. Nullable FK.
    recommendation_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("recommendations.id", ondelete="SET NULL"), nullable=True, index=True
    )
    symbol: Mapped[str] = mapped_column(String(32), index=True)
    asset_type: Mapped[str] = mapped_column(String(16), default="stock")
    side: Mapped[str] = mapped_column(String(8))  # buy / sell
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 4))
    price: Mapped[Decimal] = mapped_column(Numeric(18, 4))
    alpaca_order_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="filled")
    executed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    portfolio: Mapped[Portfolio] = relationship(back_populates="trades")
