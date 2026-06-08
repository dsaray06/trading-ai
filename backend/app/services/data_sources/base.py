"""Internal interfaces and normalized models for market-data sources.

Agents depend on these abstractions, never on a vendor SDK. Each provider gets
its own adapter (one file) implementing the relevant Protocol and returning the
normalized models defined here. See docs/06-data-sources.md.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class PriceBar:
    """One daily OHLCV bar, normalized across providers."""

    day: date
    open: float
    high: float
    low: float
    close: float
    volume: float


@dataclass(frozen=True)
class Fundamentals:
    """Normalized company fundamentals. Every metric is optional — providers
    differ in coverage, and agents must degrade gracefully when fields are missing."""

    symbol: str
    name: str | None = None
    sector: str | None = None
    market_cap: float | None = None
    pe: float | None = None
    forward_pe: float | None = None
    pb: float | None = None
    profit_margin: float | None = None  # fraction, e.g. 0.25
    revenue_growth: float | None = None  # fraction yoy
    earnings_growth: float | None = None  # fraction yoy
    debt_to_equity: float | None = None  # often a percentage (e.g. 120 == 120%)
    roe: float | None = None  # fraction
    free_cash_flow: float | None = None

    def available_metrics(self) -> dict[str, float]:
        """Non-null numeric metrics, for the UI/peer-comparison payload."""
        keys = (
            "market_cap", "pe", "forward_pe", "pb", "profit_margin",
            "revenue_growth", "earnings_growth", "debt_to_equity", "roe",
            "free_cash_flow",
        )
        return {k: getattr(self, k) for k in keys if getattr(self, k) is not None}


@dataclass(frozen=True)
class NewsItem:
    """One news headline, normalized across providers."""

    title: str
    publisher: str | None = None
    link: str | None = None
    published: datetime | None = None


@dataclass(frozen=True)
class AnalystRecommendations:
    """Analyst rating distribution (most recent period)."""

    strong_buy: int = 0
    buy: int = 0
    hold: int = 0
    sell: int = 0
    strong_sell: int = 0

    @property
    def total(self) -> int:
        return self.strong_buy + self.buy + self.hold + self.sell + self.strong_sell


@dataclass
class SentimentData:
    """Everything the Sentiment agent needs, fetched together."""

    news: list[NewsItem] = field(default_factory=list)
    analysts: AnalystRecommendations | None = None


@dataclass(frozen=True)
class OptionContract:
    """One option contract, normalized across providers."""

    contract_symbol: str
    underlying: str
    opt_type: str  # "call" | "put"
    strike: float
    expiry: date
    dte: int
    premium: float  # mid price, or last if no quote
    bid: float | None = None
    ask: float | None = None
    implied_volatility: float | None = None
    volume: int | None = None
    open_interest: int | None = None


@dataclass(frozen=True)
class OptionChain:
    """The calls and puts for one expiration, plus the underlying spot."""

    underlying: str
    spot: float
    expiry: date
    dte: int
    calls: list[OptionContract] = field(default_factory=list)
    puts: list[OptionContract] = field(default_factory=list)


class DataSourceError(RuntimeError):
    """Raised at the adapter boundary when a provider fails or returns no data.

    Agents should catch this and abstain rather than crash the whole run.
    """


@runtime_checkable
class PriceDataSource(Protocol):
    """Historical daily price bars for an equity/ETF symbol."""

    def get_daily_bars(self, symbol: str, lookback_days: int = 365) -> list[PriceBar]:
        """Return daily bars (oldest first) covering ~`lookback_days` calendar days."""
        ...


@runtime_checkable
class FundamentalsSource(Protocol):
    """Company fundamentals for an equity symbol."""

    def get_fundamentals(self, symbol: str) -> Fundamentals:
        """Return normalized fundamentals; raise DataSourceError if unavailable."""
        ...


@runtime_checkable
class NewsSource(Protocol):
    """Recent news and analyst sentiment for an equity symbol."""

    def get_sentiment_data(self, symbol: str, limit: int = 20) -> SentimentData:
        """Return recent news + analyst ratings; raise DataSourceError if unavailable."""
        ...


@runtime_checkable
class OptionsSource(Protocol):
    """Option chains for an equity symbol."""

    def get_option_chain(self, symbol: str, target_dte: int = 30) -> OptionChain:
        """Return the chain for the expiry nearest `target_dte`; raise if unavailable."""
        ...
