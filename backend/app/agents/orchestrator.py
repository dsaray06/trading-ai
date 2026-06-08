"""LangGraph orchestrator.

Defines the agent graph: a single fan-out from START to the three analysis
agents (Market, Fundamental, Sentiment), then a fan-in to the Trade Decision
node which aggregates their votes and writes the final recommendation
(docs/02-architecture.md, docs/03-agents.md).

Each analysis node is resilient: if its data source is unavailable it emits an
*abstaining* vote rather than failing the whole run. Data sources are injected so
the graph is testable with fakes.
"""
from __future__ import annotations

import operator
from typing import Annotated, TypedDict

from langgraph.graph import END, START, StateGraph

from app.agents import scoring
from app.agents.fundamental import run_fundamental_agent
from app.agents.market import run_market_agent
from app.agents.options import run_options_agent
from app.agents.sentiment import run_sentiment_agent
from app.agents.trade_decision import decide
from app.core.logging import get_logger
from app.schemas.agents import AgentVote, TradeDecision
from app.services.data_sources.base import (
    FundamentalsSource,
    NewsSource,
    OptionsSource,
    PriceDataSource,
)
from app.services.indicators import compute_indicators

logger = get_logger(__name__)

# Minimum daily bars for a full indicator set (SMA-50 + MACD-26).
_MIN_BARS = 60


def _merge_dict(a: dict, b: dict) -> dict:
    return {**a, **b}


class ResearchState(TypedDict, total=False):
    ticker: str
    asset_type: str
    include_options: bool
    reference_price: float | None
    votes: Annotated[list[AgentVote], operator.add]
    analysis: Annotated[dict, _merge_dict]
    decision: TradeDecision


def _abstain_vote(agent: str, reason: str) -> AgentVote:
    return AgentVote(agent=agent, action="Hold", score=50.0, abstain=True, reasoning=reason)


def build_research_graph(
    price_source: PriceDataSource,
    fundamentals_source: FundamentalsSource,
    news_source: NewsSource,
    options_source: OptionsSource,
):
    """Compile the research graph with the given data sources injected into nodes."""

    def market_node(state: ResearchState) -> dict:
        ticker, asset_type = state["ticker"], state["asset_type"]
        try:
            bars = price_source.get_daily_bars(ticker, lookback_days=400)
            if len(bars) < _MIN_BARS:
                raise ValueError(f"only {len(bars)} bars, need {_MIN_BARS}")
            indicators = compute_indicators([b.close for b in bars])
            out = run_market_agent(ticker, indicators, asset_type=asset_type)
            return {
                "votes": [out.vote],
                "analysis": {"technical": indicators.to_dict()},
                "reference_price": indicators.last_price,
            }
        except Exception as exc:  # noqa: BLE001 - abstain instead of failing the run
            logger.warning("market agent abstained for %s: %s", ticker, exc)
            return {"votes": [_abstain_vote("market", f"Price data unavailable: {exc}")]}

    def fundamental_node(state: ResearchState) -> dict:
        ticker = state["ticker"]
        try:
            fundamentals = fundamentals_source.get_fundamentals(ticker)
            out = run_fundamental_agent(ticker, fundamentals)
            return {
                "votes": [out.vote],
                "analysis": {"fundamental": {
                    "fundamental_score": out.fundamental_score,
                    "valuation_score": out.valuation_score,
                    "quality_score": out.quality_score,
                    "financial_health_score": out.financial_health_score,
                    "metrics": out.peer_comparison.get("metrics", {}),
                }},
            }
        except Exception as exc:  # noqa: BLE001 - abstain instead of failing the run
            logger.warning("fundamental agent abstained for %s: %s", ticker, exc)
            return {"votes": [_abstain_vote("fundamental", f"Fundamentals unavailable: {exc}")]}

    def sentiment_node(state: ResearchState) -> dict:
        ticker = state["ticker"]
        try:
            data = news_source.get_sentiment_data(ticker)
            out = run_sentiment_agent(ticker, data)
            return {
                "votes": [out.vote],
                "analysis": {"sentiment": {
                    "sentiment_score": out.sentiment_score,
                    "risk_score": out.risk_score,
                    "catalyst_score": out.catalyst_score,
                    "catalysts": out.catalysts,
                    "risks": out.risks,
                    "news_summary": out.news_summary,
                }},
            }
        except Exception as exc:  # noqa: BLE001 - abstain instead of failing the run
            logger.warning("sentiment agent abstained for %s: %s", ticker, exc)
            return {"votes": [_abstain_vote("sentiment", f"News/sentiment unavailable: {exc}")]}

    def options_node(state: ResearchState) -> dict:
        ticker = state["ticker"]
        wants_options = state.get("include_options") or state["asset_type"] == "option"
        if not wants_options:
            return {"votes": [_abstain_vote("options", "Options not requested.")]}
        try:
            bars = price_source.get_daily_bars(ticker, lookback_days=400)
            if len(bars) < _MIN_BARS:
                raise ValueError(f"only {len(bars)} bars")
            indicators = compute_indicators([b.close for b in bars])
            strength = scoring.technical_score(indicators)
            chain = options_source.get_option_chain(ticker)
            out = run_options_agent(ticker, chain, bullish=strength >= 50.0, strength=strength)
            return {
                "votes": [out.vote],
                "analysis": {"options": {
                    "action": out.vote.action,
                    "options_score": out.options_score,
                    "strike": out.strike_recommendation,
                    "expiration": out.expiration_recommendation,
                    "premium": out.premium,
                    "contract_symbol": out.contract_symbol,
                    "stop_loss": out.stop_loss,
                    "take_profit": out.take_profit,
                    "contracts": out.contracts,
                    "implied_volatility": out.implied_volatility,
                    "greeks": out.greeks,
                    "risk_reward": out.risk_reward,
                    "recommended_contracts": out.recommended_contracts,
                    "abstain": out.vote.abstain,
                }},
            }
        except Exception as exc:  # noqa: BLE001 - abstain instead of failing the run
            logger.warning("options agent abstained for %s: %s", ticker, exc)
            return {"votes": [_abstain_vote("options", f"Options unavailable: {exc}")]}

    def decision_node(state: ResearchState) -> dict:
        analysis = state.get("analysis", {})
        options = analysis.get("options")
        if options and options.get("abstain"):
            options = None
        td = decide(
            state["ticker"],
            state["votes"],
            asset_type=state["asset_type"],
            reference_price=state.get("reference_price"),
            options=options,
        )
        return {"decision": td}

    graph = StateGraph(ResearchState)
    graph.add_node("market", market_node)
    graph.add_node("fundamental", fundamental_node)
    graph.add_node("sentiment", sentiment_node)
    graph.add_node("options", options_node)
    graph.add_node("decision", decision_node)

    for agent in ("market", "fundamental", "sentiment", "options"):
        graph.add_edge(START, agent)         # fan-out
        graph.add_edge(agent, "decision")    # fan-in
    graph.add_edge("decision", END)

    return graph.compile()


def run_pipeline(
    ticker: str,
    asset_type: str,
    price_source: PriceDataSource,
    fundamentals_source: FundamentalsSource,
    news_source: NewsSource,
    options_source: OptionsSource,
    include_options: bool = False,
) -> tuple[TradeDecision, dict]:
    """Run the full agent graph and return the decision + per-agent analysis."""
    graph = build_research_graph(
        price_source, fundamentals_source, news_source, options_source
    )
    final = graph.invoke({
        "ticker": ticker.upper().strip(),
        "asset_type": asset_type,
        "include_options": include_options,
        "votes": [],
        "analysis": {},
    })
    return final["decision"], final.get("analysis", {})
