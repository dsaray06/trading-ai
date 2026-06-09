"""Portfolio request/response schemas (docs/05-api-spec.md)."""
from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class PortfolioCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    starting_cash: float = Field(gt=0, default=100_000.0)
    broker: Literal["simulated", "alpaca"] = "simulated"


class PortfolioOut(BaseModel):
    id: UUID
    name: str
    broker: str
    starting_cash: float
    cash_balance: float
    created_at: datetime


class PositionOut(BaseModel):
    id: UUID
    symbol: str
    asset_type: str
    quantity: float
    avg_cost: float
    current_price: float
    market_value: float
    unrealized_pl: float
    unrealized_pct: float
    weight_pct: float


class TradeOut(BaseModel):
    id: UUID
    symbol: str
    asset_type: str
    side: str
    quantity: float
    price: float
    status: str
    recommendation_id: UUID | None
    executed_at: datetime


class AcceptTradeRequest(BaseModel):
    recommendation_id: UUID
    quantity: float | None = Field(default=None, gt=0)
    override_price: float | None = Field(default=None, gt=0)


class TradePreview(BaseModel):
    """What an auto-sized paper trade would look like, before the user commits."""

    side: str
    symbol: str
    asset_type: str
    suggested_quantity: float
    price: float           # per share, or per-contract premium for options
    multiplier: int        # 100 for options, 1 otherwise
    estimated_cost: float  # quantity * price * multiplier
    pct_of_portfolio: float
    cash_balance: float
    note: str


class PortfolioSummary(BaseModel):
    id: UUID
    name: str
    cash_balance: float
    positions_value: float
    total_value: float
    total_unrealized_pl: float
    total_pl: float  # total_value - starting_cash
    num_positions: int
    risk: dict


class AllocationSlice(BaseModel):
    label: str
    value: float
    pct: float


class AllocationOut(BaseModel):
    by_symbol: list[AllocationSlice]
    by_asset_type: list[AllocationSlice]


class HoldingReviewItem(BaseModel):
    symbol: str
    action: str
    unrealized_pct: float
    position_risk_score: float
    concentration_flags: list[str]
    rebalancing_suggestions: list[str]
    reasoning: str


class ReviewResponse(BaseModel):
    portfolio_id: UUID
    reviews: list[HoldingReviewItem]
    risk: dict
