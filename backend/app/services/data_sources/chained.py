"""Fallback chains: try each source in order until one returns data.

Lets us prefer a keyed provider (Finnhub/Polygon) but fall back to yfinance when
it's not configured or temporarily unavailable, without the agents knowing or
caring. When *all* sources fail, the raised error names each source's failure so
the cause is visible (e.g. a Polygon 403 hidden behind a yfinance fallback).
"""
from __future__ import annotations

from app.core.logging import get_logger
from app.services.data_sources.base import (
    DataSourceError,
    Fundamentals,
    FundamentalsSource,
    NewsSource,
    OptionChain,
    OptionsSource,
    SentimentData,
)

logger = get_logger(__name__)


def _combined_error(
    label: str, symbol: str, errors: list[tuple[str, Exception]]
) -> DataSourceError:
    parts = "; ".join(f"{name}: {err}" for name, err in errors)
    return DataSourceError(f"all {label} sources failed for {symbol} — {parts}")


class ChainedFundamentalsSource:
    def __init__(self, sources: list[FundamentalsSource]) -> None:
        self._sources = sources

    def get_fundamentals(self, symbol: str) -> Fundamentals:
        errors: list[tuple[str, Exception]] = []
        for source in self._sources:
            try:
                return source.get_fundamentals(symbol)
            except DataSourceError as exc:
                errors.append((type(source).__name__, exc))
        raise _combined_error("fundamentals", symbol, errors)


class ChainedNewsSource:
    def __init__(self, sources: list[NewsSource]) -> None:
        self._sources = sources

    def get_sentiment_data(self, symbol: str, limit: int = 20) -> SentimentData:
        errors: list[tuple[str, Exception]] = []
        for source in self._sources:
            try:
                return source.get_sentiment_data(symbol, limit)
            except DataSourceError as exc:
                errors.append((type(source).__name__, exc))
        raise _combined_error("news", symbol, errors)


class ChainedOptionsSource:
    def __init__(self, sources: list[OptionsSource]) -> None:
        self._sources = sources

    def get_option_chain(self, symbol: str, target_dte: int = 30) -> OptionChain:
        errors: list[tuple[str, Exception]] = []
        for source in self._sources:
            try:
                return source.get_option_chain(symbol, target_dte)
            except DataSourceError as exc:
                errors.append((type(source).__name__, exc))
        raise _combined_error("options", symbol, errors)
