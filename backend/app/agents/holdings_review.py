"""Holdings Review agent.

Evaluates an existing position: unrealized P/L, concentration, and whether to
hold / add / trim / sell / hedge. Numbers are deterministic; the explanation is
LLM-written with a templated fallback (docs/03-agents.md §5).
"""
from __future__ import annotations

from dataclasses import dataclass

from app.core.llm import get_llm_client
from app.schemas.agents import AgentVote, HoldingsReviewOutput

AGENT_NAME = "holdings"

_SYSTEM_PROMPT = (
    "You are the Holdings Review agent in a paper-trading platform. In 2-3 sentences, "
    "explain a recommendation for an existing position to a retail investor, grounded in "
    "the unrealized P/L and concentration figures provided; never invent numbers. "
    "Respond in plain text only: no Markdown, no headings, no bullet points."
)

_CONCENTRATION_LIMIT = 0.40  # flag positions above 40% of portfolio value


@dataclass(frozen=True)
class PositionView:
    symbol: str
    quantity: float
    avg_cost: float
    current_price: float
    portfolio_value: float  # total portfolio market value (incl. cash)


def _clamp(x: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, x))


def review_position(p: PositionView) -> tuple[str, float, float, list[str], list[str]]:
    """Deterministic review: (action, unrealized_pct, risk_score, flags, suggestions)."""
    unrealized_pct = (
        (p.current_price - p.avg_cost) / p.avg_cost * 100.0 if p.avg_cost else 0.0
    )
    position_value = p.quantity * p.current_price
    weight = position_value / p.portfolio_value if p.portfolio_value > 0 else 0.0

    flags: list[str] = []
    suggestions: list[str] = []
    if weight > _CONCENTRATION_LIMIT:
        flags.append(f"{p.symbol} is {weight * 100:.0f}% of the portfolio (>40%)")
        suggestions.append(f"Trim {p.symbol} toward 30% or less of the portfolio")

    if weight > 0.45:
        action = "Trim"
    elif unrealized_pct <= -25:
        action = "Sell"
    elif unrealized_pct >= 25 and weight > 0.30:
        action = "Trim"
    elif unrealized_pct >= 8 and weight < 0.15:
        action = "Add"
    else:
        action = "Hold"

    risk_score = _clamp(35.0 + weight * 60.0 + max(0.0, -unrealized_pct) * 0.5)
    return action, round(unrealized_pct, 2), round(risk_score, 2), flags, suggestions


def _template_reasoning(p: PositionView, action: str, unrealized_pct: float) -> str:
    direction = "up" if unrealized_pct >= 0 else "down"
    return (
        f"{p.symbol} is {direction} {abs(unrealized_pct):.1f}% from an average cost of "
        f"${p.avg_cost:.2f} (now ${p.current_price:.2f}). Recommendation: {action}."
    )


def run_holdings_review(p: PositionView, asset_type: str = "stock") -> HoldingsReviewOutput:
    action, unrealized_pct, risk_score, flags, suggestions = review_position(p)

    reasoning = get_llm_client().generate_reasoning(
        system=_SYSTEM_PROMPT,
        prompt=(
            f"Position: {p.symbol} ({asset_type}), qty {p.quantity}, avg cost "
            f"${p.avg_cost:.2f}, current ${p.current_price:.2f}.\n"
            f"Unrealized P/L: {unrealized_pct:.1f}%. Concentration flags: {flags or 'none'}. "
            f"Recommendation: {action}.\nWrite the explanation."
        ),
        max_tokens=250,
    )
    if reasoning is None:
        reasoning = _template_reasoning(p, action, unrealized_pct)

    vote = AgentVote(agent=AGENT_NAME, action=action,
                     score=round(100.0 - risk_score, 2), reasoning=reasoning)
    return HoldingsReviewOutput(
        action=action,
        unrealized_pct=unrealized_pct,
        position_risk_score=risk_score,
        concentration_flags=flags,
        rebalancing_suggestions=suggestions,
        vote=vote,
        reasoning=reasoning,
    )
