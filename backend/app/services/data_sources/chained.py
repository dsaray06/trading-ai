"""Fallback chains: try each source in order until one returns data.

Lets us prefer a keyed provider (Finnhub) but fall back to yfinance when it's
not configured or temporarily unavailable, without the agents knowing or caring.
"""
from __future__ import annotations

from app.core.logging import get_logger
from app.services.data_sources.base import (
    DataSourceError,
    Fundamentals,
    FundamentalsSource,
    NewsSource,
    SentimentData,
)

logger = get_logger(__name__)


class ChainedFundamentalsSource:
    def __init__(self, sources: list[FundamentalsSource]) -> None:
        self._sources = sources

    def get_fundamentals(self, symbol: str) -> Fundamentals:
        last: DataSourceError | None = None
        for source in self._sources:
            try:
                return source.get_fundamentals(symbol)
            except DataSourceError as exc:
                last = exc
                continue
        raise last or DataSourceError(f"no fundamentals source for {symbol}")


class ChainedNewsSource:
    def __init__(self, sources: list[NewsSource]) -> None:
        self._sources = sources

    def get_sentiment_data(self, symbol: str, limit: int = 20) -> SentimentData:
        last: DataSourceError | None = None
        for source in self._sources:
            try:
                return source.get_sentiment_data(symbol, limit)
            except DataSourceError as exc:
                last = exc
                continue
        raise last or DataSourceError(f"no news source for {symbol}")
