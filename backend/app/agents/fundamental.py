"""Fundamental Analysis agent.

Scores a company's valuation, quality, growth, and balance-sheet health from
normalized fundamentals — deterministically — then attaches a vote and an
LLM-written explanation (templated fallback when the LLM is unavailable).
Abstains when no fundamentals are available (docs/03-agents.md, docs/06).
"""
from __future__ import annotations

from dataclasses import dataclass

from app.core.llm import get_llm_client
from app.schemas.agents import AgentVote, FundamentalAnalysisOutput
from app.services.data_sources.base import Fundamentals

AGENT_NAME = "fundamental"

_SYSTEM_PROMPT = (
    "You are the Fundamental Analysis agent in a paper-trading research platform. "
    "Explain a company's fundamental picture in 2-3 sentences for a retail investor, "
    "grounded strictly in the metrics provided; never invent numbers. "
    "Be concise and neutral. Do not give financial advice. "
    "Respond in plain text only: no Markdown, no headings, no bullet points."
)

# Component weights for the composite score; renormalized over available pieces.
_WEIGHTS = {"valuation": 0.30, "quality": 0.25, "growth": 0.25, "financial_health": 0.20}


def _clamp(x: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, x))


def _higher_better(x: float, bad: float, good: float) -> float:
    """Linear map: x<=bad -> 0, x>=good -> 100."""
    if good == bad:
        return 50.0
    return _clamp((x - bad) / (good - bad) * 100.0)


def _lower_better(x: float, good: float, bad: float) -> float:
    """Linear map: x<=good -> 100, x>=bad -> 0."""
    if good == bad:
        return 50.0
    return _clamp((bad - x) / (bad - good) * 100.0)


def _avg(values: list[float | None]) -> float | None:
    present = [v for v in values if v is not None]
    return sum(present) / len(present) if present else None


@dataclass(frozen=True)
class FundamentalScores:
    valuation: float | None
    quality: float | None
    growth: float | None
    financial_health: float | None
    composite: float | None


def score_fundamentals(f: Fundamentals) -> FundamentalScores:
    """Deterministic 0-100 sub-scores + weighted composite. Pure & testable."""
    valuation = _avg([
        _lower_better(f.pe, good=15, bad=45) if f.pe is not None and f.pe > 0 else None,
        _lower_better(f.pb, good=1.0, bad=8) if f.pb is not None and f.pb > 0 else None,
    ])
    quality = _avg([
        _higher_better(f.profit_margin, bad=0.0, good=0.25)
        if f.profit_margin is not None else None,
        _higher_better(f.roe, bad=0.0, good=0.25) if f.roe is not None else None,
    ])
    growth = _avg([
        _higher_better(f.revenue_growth, bad=0.0, good=0.20)
        if f.revenue_growth is not None else None,
        _higher_better(f.earnings_growth, bad=0.0, good=0.25)
        if f.earnings_growth is not None else None,
    ])
    financial_health = (
        _lower_better(f.debt_to_equity, good=40, bad=250)
        if f.debt_to_equity is not None else None
    )

    parts = {
        "valuation": valuation,
        "quality": quality,
        "growth": growth,
        "financial_health": financial_health,
    }
    weighted = [(_WEIGHTS[k], v) for k, v in parts.items() if v is not None]
    total_w = sum(w for w, _ in weighted)
    composite = sum(w * v for w, v in weighted) / total_w if total_w > 0 else None

    return FundamentalScores(
        valuation=valuation,
        quality=quality,
        growth=growth,
        financial_health=financial_health,
        composite=composite,
    )


def _action_for_score(score: float) -> str:
    if score >= 65:
        return "Buy"
    if score >= 45:
        return "Hold"
    return "Sell"


def _abstain(reason: str) -> FundamentalAnalysisOutput:
    vote = AgentVote(agent=AGENT_NAME, action="Hold", score=50.0, abstain=True,
                     reasoning=reason)
    return FundamentalAnalysisOutput(
        fundamental_score=50.0, quality_score=50.0, valuation_score=50.0,
        financial_health_score=50.0, peer_comparison={}, vote=vote, reasoning=reason,
    )


def _template_reasoning(ticker: str, f: Fundamentals, s: FundamentalScores) -> str:
    bits = []
    if f.pe is not None:
        bits.append(f"P/E {f.pe:.1f}")
    if f.profit_margin is not None:
        bits.append(f"margin {f.profit_margin * 100:.0f}%")
    if f.revenue_growth is not None:
        bits.append(f"rev growth {f.revenue_growth * 100:.0f}%")
    metrics = ", ".join(bits) if bits else "limited metrics"
    return (
        f"{ticker} shows {metrics}, yielding a fundamental score of "
        f"{s.composite:.0f}/100 (valuation {s.valuation or 50:.0f}, quality "
        f"{s.quality or 50:.0f}). On fundamentals this leans "
        f"{_action_for_score(s.composite)}."
    )


def run_fundamental_agent(ticker: str, fundamentals: Fundamentals) -> FundamentalAnalysisOutput:
    """Score fundamentals and emit a vote + explanation, abstaining if data is thin."""
    s = score_fundamentals(fundamentals)
    if s.composite is None:
        return _abstain(f"No usable fundamentals available for {ticker}; abstaining.")

    action = _action_for_score(s.composite)
    reasoning = get_llm_client().generate_reasoning(
        system=_SYSTEM_PROMPT,
        prompt=(
            f"Ticker: {ticker}\n"
            f"Fundamentals: {fundamentals.available_metrics()}\n"
            f"Computed scores -> composite: {s.composite:.1f}, valuation: {s.valuation}, "
            f"quality: {s.quality}, growth: {s.growth}, health: {s.financial_health}, "
            f"leaning: {action}.\nWrite the explanation."
        ),
        max_tokens=300,
    )
    if reasoning is None:
        reasoning = _template_reasoning(ticker, fundamentals, s)

    vote = AgentVote(agent=AGENT_NAME, action=action, score=round(s.composite, 2),
                     reasoning=reasoning)
    return FundamentalAnalysisOutput(
        fundamental_score=round(s.composite, 2),
        quality_score=round(s.quality if s.quality is not None else 50.0, 2),
        valuation_score=round(s.valuation if s.valuation is not None else 50.0, 2),
        financial_health_score=round(
            s.financial_health if s.financial_health is not None else 50.0, 2
        ),
        peer_comparison={"metrics": fundamentals.available_metrics()},
        vote=vote,
        reasoning=reasoning,
    )
