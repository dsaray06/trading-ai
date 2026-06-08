"""Request/response schemas for the research endpoint (docs/05-api-spec.md)."""
from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

DISCLAIMER = "Research / paper trading only. Not financial advice."


class ResearchRequest(BaseModel):
    asset_type: Literal["stock", "etf", "option"] = "stock"
    horizon: Literal["short", "medium", "long"] = "medium"
    include_options: bool = False


class AgentVoteOut(BaseModel):
    agent: str
    action: str
    score: float
    weight: float
    reasoning: str


class RecommendationResponse(BaseModel):
    id: UUID
    ticker: str
    asset_type: str
    action: str
    entry_target: float | None = None
    exit_target: float | None = None
    stop_loss: float | None = None
    take_profit: float | None = None
    position_size: float | None = None
    confidence: float = Field(ge=0, le=100)
    thesis: str
    reasoning_report: str
    agent_votes: list[AgentVoteOut]
    analysis: dict
    disclaimer: str = DISCLAIMER
