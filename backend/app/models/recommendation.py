"""ORM models for recommendations and their per-agent vote breakdown.

Mirrors the `recommendations` and `agent_votes` tables in docs/04-data-model.md
and the `TradeDecision` / `AgentVote` contracts in docs/03-agents.md.

Phase 1 note: auth (users) and portfolios arrive in Phase 3, so `user_id` and
`portfolio_id` are nullable here and their FK constraints are added when those
tables land. Everything else matches the target schema.
"""
from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from sqlalchemy import JSON, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, new_uuid


class Recommendation(Base, TimestampMixin):
    __tablename__ = "recommendations"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_uuid)
    # FK constraints to users/portfolios are added in Phase 3 (auth).
    user_id: Mapped[UUID | None] = mapped_column(nullable=True)
    portfolio_id: Mapped[UUID | None] = mapped_column(nullable=True)

    symbol: Mapped[str] = mapped_column(String(32), index=True)
    asset_type: Mapped[str] = mapped_column(String(16))
    action: Mapped[str] = mapped_column(String(16))

    entry_target: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    exit_target: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    stop_loss: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    take_profit: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    position_size: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)

    confidence: Mapped[Decimal] = mapped_column(Numeric(5, 2))
    thesis: Mapped[str] = mapped_column(Text)
    reasoning_report: Mapped[str] = mapped_column(Text)

    votes: Mapped[list[AgentVoteRow]] = relationship(
        back_populates="recommendation",
        cascade="all, delete-orphan",
        order_by="AgentVoteRow.agent",
    )


class AgentVoteRow(Base, TimestampMixin):
    __tablename__ = "agent_votes"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_uuid)
    recommendation_id: Mapped[UUID] = mapped_column(
        ForeignKey("recommendations.id", ondelete="CASCADE"), index=True
    )

    agent: Mapped[str] = mapped_column(String(32))
    action: Mapped[str] = mapped_column(String(16))
    score: Mapped[Decimal] = mapped_column(Numeric(5, 2))
    weight: Mapped[Decimal] = mapped_column(Numeric(5, 4))
    reasoning: Mapped[str] = mapped_column(Text)
    raw_output: Mapped[dict] = mapped_column(JSON, default=dict)

    recommendation: Mapped[Recommendation] = relationship(back_populates="votes")
