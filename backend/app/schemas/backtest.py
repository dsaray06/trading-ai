"""Backtest request/response schemas (docs/05-api-spec.md)."""
from __future__ import annotations

from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

Horizon = Literal["1Y", "3Y", "5Y", "10Y"]
Benchmark = Literal["SPY", "QQQ", "VTI", "custom"]


class BacktestRequest(BaseModel):
    strategy: str = "sma_crossover"
    symbol: str = Field(default="AAPL", max_length=16)
    benchmark: Benchmark = "SPY"
    benchmark_symbol: str | None = None  # required when benchmark == "custom"
    horizon: Horizon = "3Y"
    params: dict = Field(default_factory=dict)


class EquityPoint(BaseModel):
    date: str
    strategy: float
    benchmark: float


class BacktestOut(BaseModel):
    id: UUID
    strategy: str
    strategy_label: str
    symbol: str
    benchmark: str
    horizon: str
    start_date: date
    end_date: date
    metrics: dict
    equity_curve: list[EquityPoint]
    created_at: datetime


class BacktestSummary(BaseModel):
    id: UUID
    strategy: str
    strategy_label: str
    symbol: str
    benchmark: str
    horizon: str
    metrics: dict
    created_at: datetime


class CompareRequest(BaseModel):
    backtest_ids: list[UUID] = Field(min_length=1, max_length=8)


class CompareItem(BaseModel):
    id: UUID
    strategy: str
    strategy_label: str
    symbol: str
    metrics: dict


class CompareResponse(BaseModel):
    items: list[CompareItem]
