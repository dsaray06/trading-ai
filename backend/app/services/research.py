"""Research orchestration service.

Phase 2: runs the LangGraph agent graph (Market + Fundamental + Sentiment ->
Trade Decision), persists the recommendation + every agent vote, and maps the
result to the API response. Route handlers call `run_research`.
"""
from __future__ import annotations

from decimal import Decimal

from sqlalchemy.orm import Session

from app.agents.orchestrator import run_pipeline
from app.core.config import get_settings
from app.core.logging import get_logger
from app.models.recommendation import AgentVoteRow, Recommendation
from app.schemas.research import (
    DISCLAIMER,
    AgentVoteOut,
    RecommendationResponse,
    ResearchRequest,
)
from app.services.data_sources.base import (
    FundamentalsSource,
    NewsSource,
    OptionsSource,
    PriceDataSource,
)
from app.services.data_sources.chained import (
    ChainedFundamentalsSource,
    ChainedNewsSource,
)
from app.services.data_sources.finnhub_source import (
    FinnhubFundamentalsSource,
    FinnhubNewsSource,
)
from app.services.data_sources.yfinance_source import (
    YFinanceFundamentalsSource,
    YFinanceNewsSource,
    YFinanceOptionsSource,
    YFinancePriceSource,
)

logger = get_logger(__name__)

_OPTIONS_ACTIONS = {"Buy Call", "Buy Put"}


def _default_fundamentals_source() -> FundamentalsSource:
    """Finnhub primary (works on cloud), yfinance fallback — if Finnhub is keyed."""
    if get_settings().finnhub_api_key:
        return ChainedFundamentalsSource(
            [FinnhubFundamentalsSource(), YFinanceFundamentalsSource()]
        )
    return YFinanceFundamentalsSource()


def _default_news_source() -> NewsSource:
    if get_settings().finnhub_api_key:
        return ChainedNewsSource([FinnhubNewsSource(), YFinanceNewsSource()])
    return YFinanceNewsSource()


class ResearchError(RuntimeError):
    """Raised when research can't be produced (e.g. unknown ticker / no data)."""


def _to_decimal(value: float | None) -> Decimal | None:
    return None if value is None else Decimal(str(round(value, 4)))


# Map each agent to the analysis section persisted in its vote's raw_output.
_ANALYSIS_KEY = {
    "market": "technical", "fundamental": "fundamental",
    "sentiment": "sentiment", "options": "options",
}


def run_research(
    db: Session,
    ticker: str,
    request: ResearchRequest,
    price_source: PriceDataSource | None = None,
    fundamentals_source: FundamentalsSource | None = None,
    news_source: NewsSource | None = None,
    options_source: OptionsSource | None = None,
) -> RecommendationResponse:
    """Produce, persist, and return a multi-agent recommendation for `ticker`."""
    ticker = ticker.upper().strip()
    include_options = request.include_options or request.asset_type == "option"

    decision, analysis = run_pipeline(
        ticker,
        request.asset_type,
        price_source or YFinancePriceSource(),
        fundamentals_source or _default_fundamentals_source(),
        news_source or _default_news_source(),
        options_source or YFinanceOptionsSource(),
        include_options=include_options,
    )

    if all(v.abstain for v in decision.agent_votes):
        raise ResearchError(
            f"No data available for {ticker} — every agent abstained."
        )

    # An options recommendation is stored against the contract symbol so it can
    # be paper-executed directly; equity recs use the ticker.
    is_option = decision.action in _OPTIONS_ACTIONS
    opts = analysis.get("options", {}) if is_option else {}
    rec_symbol = opts.get("contract_symbol") or ticker if is_option else ticker
    rec_asset_type = "option" if is_option else request.asset_type

    rec = Recommendation(
        symbol=rec_symbol,
        asset_type=rec_asset_type,
        action=decision.action,
        entry_target=_to_decimal(decision.entry_target),
        exit_target=_to_decimal(decision.exit_target),
        stop_loss=_to_decimal(decision.stop_loss),
        take_profit=_to_decimal(decision.take_profit),
        position_size=_to_decimal(decision.position_size),
        confidence=Decimal(str(decision.confidence)),
        thesis=decision.thesis,
        reasoning_report=decision.reasoning_report,
    )
    rec.votes = [
        AgentVoteRow(
            agent=v.agent,
            action=v.action,
            score=Decimal(str(v.score)),
            weight=Decimal(str(v.weight)),
            reasoning=v.reasoning,
            raw_output=analysis.get(_ANALYSIS_KEY.get(v.agent, ""), {}) or {},
        )
        for v in decision.agent_votes
    ]
    db.add(rec)
    db.commit()
    db.refresh(rec)

    participating = sum(1 for v in decision.agent_votes if not v.abstain)
    logger.info(
        "research %s -> %s (conf %.0f, %d/%d agents voting)",
        ticker, decision.action, decision.confidence, participating, len(decision.agent_votes),
    )

    return RecommendationResponse(
        id=rec.id,
        ticker=ticker,
        asset_type=rec_asset_type,
        action=decision.action,
        entry_target=decision.entry_target,
        exit_target=decision.exit_target,
        stop_loss=decision.stop_loss,
        take_profit=decision.take_profit,
        position_size=decision.position_size,
        confidence=decision.confidence,
        thesis=decision.thesis,
        reasoning_report=decision.reasoning_report,
        agent_votes=[
            AgentVoteOut(
                agent=v.agent,
                action=v.action,
                score=v.score,
                weight=v.weight,
                reasoning=v.reasoning,
            )
            for v in decision.agent_votes
        ],
        analysis=analysis,
        disclaimer=DISCLAIMER,
    )
