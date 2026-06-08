"""Shared agent I/O schemas (Pydantic v2).

These are the typed contracts every agent and the orchestrator pass around.
Keep them in sync with docs/03-agents.md.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

# Recommendation actions used across agents and the Decision output.
Action = Literal[
    "Buy",
    "Sell",
    "Hold",
    "Add",
    "Trim",
    "Hedge",
    "Buy Call",
    "Buy Put",
    "Buy ETF",
    "Watchlist",
]

Trend = Literal["strong_up", "up", "sideways", "down", "strong_down"]


class AgentVote(BaseModel):
    """One agent's directional vote. `weight` is filled by the orchestrator."""

    agent: str
    action: str
    score: float = Field(ge=0, le=100)
    weight: float = 0.0
    abstain: bool = False
    reasoning: str = ""


class MarketAnalysisOutput(BaseModel):
    technical_score: float = Field(ge=0, le=100)
    momentum_score: float = Field(ge=0, le=100)
    volatility_score: float = Field(ge=0, le=100)
    trend: Trend
    indicators: dict
    vote: AgentVote
    reasoning: str


class FundamentalAnalysisOutput(BaseModel):
    fundamental_score: float = Field(ge=0, le=100)
    quality_score: float = Field(ge=0, le=100)
    valuation_score: float = Field(ge=0, le=100)  # higher = cheaper / better value
    financial_health_score: float = Field(ge=0, le=100)
    peer_comparison: dict
    vote: AgentVote
    reasoning: str


class SentimentAnalysisOutput(BaseModel):
    sentiment_score: float = Field(ge=0, le=100)  # higher = more positive
    risk_score: float = Field(ge=0, le=100)  # higher = more risk
    catalyst_score: float = Field(ge=0, le=100)
    news_summary: str
    catalysts: list[str]
    risks: list[str]
    vote: AgentVote
    reasoning: str


class OptionsAnalysisOutput(BaseModel):
    options_score: float = Field(ge=0, le=100)
    recommended_contracts: list[dict]
    strike_recommendation: float
    expiration_recommendation: str  # e.g. "32 DTE (2026-07-10)"
    risk_reward: dict               # max_gain, max_loss, breakeven, ratio
    contract_symbol: str
    premium: float
    stop_loss: float | None = None
    take_profit: float | None = None
    contracts: int = 1
    greeks: dict
    implied_volatility: float | None = None
    vote: AgentVote                 # Buy Call / Buy Put (or abstain)
    reasoning: str


class HoldingsReviewOutput(BaseModel):
    action: Literal["Hold", "Add", "Trim", "Sell", "Hedge"]
    unrealized_pct: float
    position_risk_score: float = Field(ge=0, le=100)
    concentration_flags: list[str]
    rebalancing_suggestions: list[str]
    vote: AgentVote
    reasoning: str


class TradeDecision(BaseModel):
    """Final aggregated recommendation. Mirrors the `recommendations` table."""

    ticker: str
    asset_type: str = "stock"
    action: Action
    entry_target: float | None = None
    exit_target: float | None = None
    stop_loss: float | None = None
    take_profit: float | None = None
    position_size: float | None = None
    confidence: float = Field(ge=0, le=100)
    agent_votes: list[AgentVote]
    thesis: str
    reasoning_report: str
    disclaimer: str = "Research / paper trading only. Not financial advice."
