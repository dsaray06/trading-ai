"""Market-data source factories (cloud-friendly, auth-aware).

Builds the price/options data sources used by both research and portfolio pricing.
Alpaca's IEX/indicative feeds work from cloud IPs and with any single account's
keys (like Finnhub), so one server-wide Alpaca key powers prices + options for
everyone; a connected user's own keys take precedence when present. yfinance is
kept as a last-resort fallback (works locally, blocked on Render's datacenter IP).
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.user import User
from app.services import alpaca_credentials
from app.services.data_sources.alpaca_options_source import AlpacaOptionsSource
from app.services.data_sources.alpaca_price_source import AlpacaPriceSource
from app.services.data_sources.base import OptionsSource, PriceDataSource
from app.services.data_sources.chained import ChainedOptionsSource, ChainedPriceSource
from app.services.data_sources.polygon_source import PolygonOptionsSource
from app.services.data_sources.yfinance_source import (
    YFinanceOptionsSource,
    YFinancePriceSource,
)


def alpaca_data_creds(db: Session, user: User | None) -> tuple[str, str] | None:
    """Alpaca keys for market data: a connected user's own keys if present, else
    the server-wide key from settings (None if neither is configured)."""
    if user is not None:
        creds = alpaca_credentials.raw_credentials(db, user)
        if creds:
            return creds
    settings = get_settings()
    if settings.alpaca_api_key and settings.alpaca_api_secret:
        return settings.alpaca_api_key, settings.alpaca_api_secret
    return None


def price_source_for(db: Session, user: User | None) -> PriceDataSource:
    """Alpaca daily bars first (works on cloud IPs), yfinance fallback."""
    creds = alpaca_data_creds(db, user)
    if creds:
        return ChainedPriceSource([AlpacaPriceSource(*creds), YFinancePriceSource()])
    return YFinancePriceSource()


def options_source_for(db: Session, user: User | None) -> OptionsSource:
    """Alpaca (free indicative feed, cloud-friendly), then Polygon (if keyed),
    then yfinance (works locally)."""
    sources: list[OptionsSource] = []
    creds = alpaca_data_creds(db, user)
    if creds:
        sources.append(AlpacaOptionsSource(*creds))
    if get_settings().polygon_api_key:
        sources.append(PolygonOptionsSource())
    sources.append(YFinanceOptionsSource())
    return sources[0] if len(sources) == 1 else ChainedOptionsSource(sources)
