"""Market Analysis agent.

Computes technical indicators and scores (deterministically), then attaches a
vote and a natural-language explanation. The numbers come from pure functions in
`app.agents.scoring`; only the prose `reasoning` comes from the LLM, with a
deterministic template fallback when the LLM is unavailable (docs/03-agents.md).
"""
from __future__ import annotations

from app.agents import scoring
from app.core.llm import get_llm_client
from app.schemas.agents import AgentVote, MarketAnalysisOutput
from app.services.indicators import IndicatorSet

AGENT_NAME = "market"

_SYSTEM_PROMPT = (
    "You are the Market Analysis agent in a paper-trading research platform. "
    "Explain the technical read on a stock in 2-3 sentences for a retail investor. "
    "Ground every statement in the indicator values provided; never invent numbers. "
    "Be concise, neutral, and explanatory. Do not give financial advice or a price target. "
    "Respond in plain text only: no Markdown, no headings, no bold, no bullet points."
)


def _template_reasoning(
    ticker: str, ind: IndicatorSet, tech: float, trend: str, action: str
) -> str:
    """Deterministic fallback explanation used when the LLM is unavailable."""
    rel_ma = "above" if ind.last_price > ind.sma_20 else "below"
    macd_dir = "bullish" if ind.macd.histogram > 0 else "bearish"
    return (
        f"{ticker} is trading {rel_ma} its 20-day average with RSI at "
        f"{ind.rsi_14:.0f} and a {macd_dir} MACD histogram, giving a technical "
        f"score of {tech:.0f}/100 and a '{trend}' trend read. On technicals alone "
        f"this leans toward a {action}."
    )


def run_market_agent(
    ticker: str, indicators: IndicatorSet, asset_type: str = "stock"
) -> MarketAnalysisOutput:
    """Score the security technically and emit a vote + explanation."""
    tech = scoring.technical_score(indicators)
    momentum = scoring.momentum_subscore(indicators)
    volatility = scoring.volatility_subscore(indicators)
    trend = scoring.classify_trend(indicators)
    action = scoring.action_for_score(tech)

    reasoning = get_llm_client().generate_reasoning(
        system=_SYSTEM_PROMPT,
        prompt=(
            f"Ticker: {ticker} ({asset_type})\n"
            f"Indicators: {indicators.to_dict()}\n"
            f"Computed scores -> technical: {tech:.1f}, momentum: {momentum:.1f}, "
            f"volatility: {volatility:.1f}, trend: {trend}, leaning: {action}.\n"
            "Write the explanation."
        ),
        max_tokens=300,
    )
    if reasoning is None:
        reasoning = _template_reasoning(ticker, indicators, tech, trend, action)

    vote = AgentVote(
        agent=AGENT_NAME, action=action, score=round(tech, 2), reasoning=reasoning
    )
    return MarketAnalysisOutput(
        technical_score=round(tech, 2),
        momentum_score=round(momentum, 2),
        volatility_score=round(volatility, 2),
        trend=trend,
        indicators=indicators.to_dict(),
        vote=vote,
        reasoning=reasoning,
    )
