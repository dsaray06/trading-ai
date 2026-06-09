"""Finnhub adapters for fundamentals and news/analyst sentiment.

Finnhub is a keyed API (works fine from cloud IPs, unlike yfinance's info/news
scraping). Requires `FINNHUB_API_KEY`. Used as the primary source for the
Fundamental and Sentiment agents in production, with yfinance as a fallback
(docs/06-data-sources.md).
"""
from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

from app.core.config import get_settings
from app.core.logging import get_logger
from app.services.cache import TTLCache
from app.services.data_sources.base import (
    AnalystRecommendations,
    DataSourceError,
    Fundamentals,
    NewsItem,
    SentimentData,
)

logger = get_logger(__name__)
_cache = TTLCache(ttl_seconds=3600.0)
# Symbol classification rarely changes — cache it for a day.
_class_cache = TTLCache(ttl_seconds=86_400.0)

# Finnhub `type` values that denote a fund / exchange-traded product (not a company
# with reportable fundamentals). Common Stock / ADR / REIT stay "stock".
_FUND_TYPES = ("ETP", "ETF", "ETN", "FUND", "UNIT", "CLOSED-END")


def make_client():
    """Build a finnhub client (lazy import). Indirection point for tests."""
    settings = get_settings()
    if not settings.finnhub_api_key:
        raise DataSourceError("Finnhub API key not configured")
    import finnhub

    return finnhub.Client(api_key=settings.finnhub_api_key)


def classify_symbol(symbol: str) -> str | None:
    """Best-effort asset classification via Finnhub symbol lookup.

    Returns "etf" for funds / exchange-traded products, "stock" for equities, or
    None when it can't be determined (no Finnhub key, network error, or no exact
    match). Lets research auto-detect ETFs (which have no company fundamentals) so
    the user doesn't have to tag them by hand. Cached for a day.
    """
    symbol = symbol.upper().strip()
    cache_key = f"fh-class:{symbol}"
    cached = _class_cache.get(cache_key)
    if cached is not None:
        return cached
    try:
        client = make_client()
        result = (client.symbol_lookup(symbol) or {}).get("result", [])
    except DataSourceError:
        return None  # no key configured
    except Exception as exc:  # noqa: BLE001 - classification is best-effort
        logger.warning("finnhub symbol lookup failed for %s: %s", symbol, exc)
        return None
    match = next((r for r in result if (r.get("symbol") or "").upper() == symbol), None)
    if match is None:
        return None
    type_ = (match.get("type") or "").upper()
    classified = "etf" if any(k in type_ for k in _FUND_TYPES) else "stock"
    _class_cache.set(cache_key, classified)
    logger.info("classified %s as %s (finnhub type=%r)", symbol, classified, type_)
    return classified


def _f(value) -> float | None:
    if value is None:
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return None if out != out else out  # drop NaN


def _pct(value) -> float | None:
    """Finnhub reports margins/growth/ROE as percentages; store as fractions."""
    f = _f(value)
    return f / 100.0 if f is not None else None


class FinnhubFundamentalsSource:
    def get_fundamentals(self, symbol: str) -> Fundamentals:
        symbol = symbol.upper().strip()
        cache_key = f"fh-fund:{symbol}"
        cached = _cache.get(cache_key)
        if cached is not None:
            return cached

        try:
            client = make_client()
            metric = (client.company_basic_financials(symbol, "all") or {}).get("metric", {})
            profile = client.company_profile2(symbol=symbol) or {}
        except DataSourceError:
            raise
        except Exception as exc:  # noqa: BLE001 - translate vendor failure
            logger.warning("finnhub fundamentals failed for %s: %s", symbol, exc)
            raise DataSourceError(f"finnhub fundamentals failed for {symbol}") from exc

        metric = metric or {}
        de_ratio = _f(
            metric.get("totalDebt/totalEquityQuarterly")
            or metric.get("totalDebt/totalEquityAnnual")
        )
        mktcap = _f(profile.get("marketCapitalization"))
        fundamentals = Fundamentals(
            symbol=symbol,
            name=profile.get("name"),
            sector=profile.get("finnhubIndustry"),
            market_cap=mktcap * 1e6 if mktcap is not None else None,  # given in millions
            pe=_f(metric.get("peTTM")),
            forward_pe=None,
            pb=_f(metric.get("pbQuarterly")) or _f(metric.get("pbAnnual")),
            profit_margin=_pct(metric.get("netProfitMarginTTM")),
            revenue_growth=_pct(metric.get("revenueGrowthTTMYoy")),
            earnings_growth=_pct(metric.get("epsGrowthTTMYoy")),
            debt_to_equity=de_ratio * 100 if de_ratio is not None else None,  # ratio -> %
            roe=_pct(metric.get("roeTTM")),
            free_cash_flow=None,
        )
        if not fundamentals.available_metrics():
            raise DataSourceError(f"no finnhub fundamentals for {symbol}")
        _cache.set(cache_key, fundamentals)
        logger.info("finnhub fundamentals for %s (%d metrics)",
                    symbol, len(fundamentals.available_metrics()))
        return fundamentals


class FinnhubNewsSource:
    def get_sentiment_data(self, symbol: str, limit: int = 20) -> SentimentData:
        symbol = symbol.upper().strip()
        cache_key = f"fh-news:{symbol}:{limit}"
        cached = _cache.get(cache_key)
        if cached is not None:
            return cached

        try:
            client = make_client()
            today = date.today()
            frm = today - timedelta(days=14)
            raw_news = client.company_news(symbol, _from=frm.isoformat(), to=today.isoformat())
            rec = client.recommendation_trends(symbol)
        except DataSourceError:
            raise
        except Exception as exc:  # noqa: BLE001 - translate vendor failure
            logger.warning("finnhub news failed for %s: %s", symbol, exc)
            raise DataSourceError(f"finnhub news failed for {symbol}") from exc

        news: list[NewsItem] = []
        for item in (raw_news or [])[:limit]:
            title = item.get("headline")
            if not title:
                continue
            ts = item.get("datetime")
            published = (
                datetime.fromtimestamp(ts, tz=UTC) if isinstance(ts, (int, float)) else None
            )
            news.append(NewsItem(title=str(title), publisher=item.get("source"),
                                 published=published))

        analysts = None
        if rec:
            r = rec[0]  # most recent period first
            analysts = AnalystRecommendations(
                strong_buy=int(r.get("strongBuy", 0) or 0),
                buy=int(r.get("buy", 0) or 0),
                hold=int(r.get("hold", 0) or 0),
                sell=int(r.get("sell", 0) or 0),
                strong_sell=int(r.get("strongSell", 0) or 0),
            )

        data = SentimentData(news=news, analysts=analysts)
        if not data.news and data.analysts is None:
            raise DataSourceError(f"no finnhub news/analysts for {symbol}")
        _cache.set(cache_key, data)
        logger.info("finnhub %d headlines + analysts=%s for %s",
                    len(news), analysts is not None, symbol)
        return data
