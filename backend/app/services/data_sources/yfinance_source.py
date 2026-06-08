"""yfinance adapters.

Implements `PriceDataSource`, `FundamentalsSource`, and `NewsSource` using the
(unofficial) yfinance API — the MVP's no-API-key data layer. Polygon/Finnhub
become primary in a later pass (docs/06-data-sources.md). Vendor errors are
translated to `DataSourceError` at this boundary so agents can abstain gracefully.
"""
from __future__ import annotations

from datetime import UTC, date, datetime

from app.core.logging import get_logger
from app.services.cache import TTLCache
from app.services.data_sources.base import (
    AnalystRecommendations,
    DataSourceError,
    Fundamentals,
    NewsItem,
    OptionChain,
    OptionContract,
    PriceBar,
    SentimentData,
)

logger = get_logger(__name__)

# 15-minute TTL: plenty fresh for daily-bar technical analysis, gentle on quotas.
_cache = TTLCache(ttl_seconds=900.0)
# Fundamentals/news move slowly — cache longer.
_meta_cache = TTLCache(ttl_seconds=3600.0)


def _f(value: object) -> float | None:
    """Coerce a possibly-missing yfinance numeric into a clean float or None."""
    if value is None:
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    # yfinance uses NaN for missing values.
    return None if out != out else out


class YFinancePriceSource:
    """Daily OHLCV bars from yfinance, normalized to `PriceBar`."""

    def get_daily_bars(self, symbol: str, lookback_days: int = 365) -> list[PriceBar]:
        symbol = symbol.upper().strip()
        cache_key = f"yf:{symbol}:{lookback_days}"
        cached = _cache.get(cache_key)
        if cached is not None:
            return cached

        bars = self._fetch(symbol, lookback_days)
        _cache.set(cache_key, bars)
        return bars

    def _fetch(self, symbol: str, lookback_days: int) -> list[PriceBar]:
        try:
            import yfinance as yf

            period = self._period_for(lookback_days)
            df = yf.Ticker(symbol).history(period=period, interval="1d", auto_adjust=True)
        except Exception as exc:  # noqa: BLE001 - translate any vendor failure
            logger.warning("yfinance fetch failed for %s: %s", symbol, exc)
            raise DataSourceError(f"yfinance fetch failed for {symbol}") from exc

        if df is None or df.empty:
            raise DataSourceError(f"no price data for {symbol}")

        bars: list[PriceBar] = []
        for ts, row in df.iterrows():
            bars.append(
                PriceBar(
                    day=date(ts.year, ts.month, ts.day),
                    open=float(row["Open"]),
                    high=float(row["High"]),
                    low=float(row["Low"]),
                    close=float(row["Close"]),
                    volume=float(row["Volume"]),
                )
            )
        logger.info("fetched %d daily bars for %s", len(bars), symbol)
        return bars

    @staticmethod
    def _period_for(lookback_days: int) -> str:
        """Map a lookback window to the nearest yfinance period string."""
        if lookback_days <= 35:
            return "1mo"
        if lookback_days <= 100:
            return "3mo"
        if lookback_days <= 200:
            return "6mo"
        if lookback_days <= 400:
            return "1y"
        if lookback_days <= 800:
            return "2y"
        if lookback_days <= 1900:
            return "5y"
        return "10y"


class YFinanceFundamentalsSource:
    """Company fundamentals from yfinance `Ticker.info`, normalized to `Fundamentals`."""

    def get_fundamentals(self, symbol: str) -> Fundamentals:
        symbol = symbol.upper().strip()
        cache_key = f"yf-fund:{symbol}"
        cached = _meta_cache.get(cache_key)
        if cached is not None:
            return cached

        try:
            import yfinance as yf

            info = yf.Ticker(symbol).info or {}
        except Exception as exc:  # noqa: BLE001 - translate any vendor failure
            logger.warning("yfinance fundamentals failed for %s: %s", symbol, exc)
            raise DataSourceError(f"yfinance fundamentals failed for {symbol}") from exc

        fundamentals = Fundamentals(
            symbol=symbol,
            name=info.get("shortName") or info.get("longName"),
            sector=info.get("sector"),
            market_cap=_f(info.get("marketCap")),
            pe=_f(info.get("trailingPE")),
            forward_pe=_f(info.get("forwardPE")),
            pb=_f(info.get("priceToBook")),
            profit_margin=_f(info.get("profitMargins")),
            revenue_growth=_f(info.get("revenueGrowth")),
            earnings_growth=_f(info.get("earningsGrowth")),
            debt_to_equity=_f(info.get("debtToEquity")),
            roe=_f(info.get("returnOnEquity")),
            free_cash_flow=_f(info.get("freeCashflow")),
        )
        if not fundamentals.available_metrics():
            raise DataSourceError(f"no fundamentals available for {symbol}")
        _meta_cache.set(cache_key, fundamentals)
        logger.info("fetched fundamentals for %s (%d metrics)",
                    symbol, len(fundamentals.available_metrics()))
        return fundamentals


class YFinanceNewsSource:
    """Recent news + analyst ratings from yfinance, normalized to `SentimentData`."""

    def get_sentiment_data(self, symbol: str, limit: int = 20) -> SentimentData:
        symbol = symbol.upper().strip()
        cache_key = f"yf-news:{symbol}:{limit}"
        cached = _meta_cache.get(cache_key)
        if cached is not None:
            return cached

        try:
            import yfinance as yf

            ticker = yf.Ticker(symbol)
            raw_news = ticker.news or []
            analysts = self._recommendations(ticker)
        except Exception as exc:  # noqa: BLE001 - translate any vendor failure
            logger.warning("yfinance news failed for %s: %s", symbol, exc)
            raise DataSourceError(f"yfinance news failed for {symbol}") from exc

        news = [item for raw in raw_news[:limit] if (item := self._news_item(raw))]
        data = SentimentData(news=news, analysts=analysts)
        if not data.news and data.analysts is None:
            raise DataSourceError(f"no news or analyst data for {symbol}")
        _meta_cache.set(cache_key, data)
        logger.info("fetched %d headlines + analysts=%s for %s",
                    len(news), analysts is not None, symbol)
        return data

    @staticmethod
    def _news_item(raw: dict) -> NewsItem | None:
        # yfinance news shape changed over versions: newer wraps fields in "content".
        content = raw.get("content") if isinstance(raw.get("content"), dict) else raw
        title = content.get("title") or raw.get("title")
        if not title:
            return None
        publisher = None
        provider = content.get("provider")
        if isinstance(provider, dict):
            publisher = provider.get("displayName")
        publisher = publisher or raw.get("publisher")
        published = None
        ts = raw.get("providerPublishTime")
        if isinstance(ts, (int, float)):
            published = datetime.fromtimestamp(ts, tz=UTC)
        return NewsItem(title=str(title), publisher=publisher, published=published)

    @staticmethod
    def _recommendations(ticker) -> AnalystRecommendations | None:
        try:
            df = ticker.recommendations
        except Exception:  # noqa: BLE001 - optional signal
            return None
        if df is None or getattr(df, "empty", True):
            return None
        try:
            row = df.iloc[0]  # most recent period ("0m")
            return AnalystRecommendations(
                strong_buy=int(row.get("strongBuy", 0) or 0),
                buy=int(row.get("buy", 0) or 0),
                hold=int(row.get("hold", 0) or 0),
                sell=int(row.get("sell", 0) or 0),
                strong_sell=int(row.get("strongSell", 0) or 0),
            )
        except Exception:  # noqa: BLE001 - tolerate schema drift
            return None


class YFinanceOptionsSource:
    """Option chains from yfinance, normalized to `OptionChain` / `OptionContract`."""

    def get_option_chain(self, symbol: str, target_dte: int = 30) -> OptionChain:
        symbol = symbol.upper().strip()
        cache_key = f"yf-opt:{symbol}:{target_dte}"
        cached = _meta_cache.get(cache_key)
        if cached is not None:
            return cached

        try:
            import yfinance as yf

            ticker = yf.Ticker(symbol)
            expiries = list(ticker.options or [])
            if not expiries:
                raise DataSourceError(f"no option expirations for {symbol}")
            expiry_str, expiry_date, dte = self._pick_expiry(expiries, target_dte)
            chain = ticker.option_chain(expiry_str)
            spot = self._spot(ticker)
            calls = self._contracts(chain.calls, symbol, "call", expiry_date, dte)
            puts = self._contracts(chain.puts, symbol, "put", expiry_date, dte)
        except DataSourceError:
            raise
        except Exception as exc:  # noqa: BLE001 - translate any vendor failure
            logger.warning("yfinance options failed for %s: %s", symbol, exc)
            raise DataSourceError(f"yfinance options failed for {symbol}") from exc

        if not calls and not puts:
            raise DataSourceError(f"empty option chain for {symbol}")
        oc = OptionChain(underlying=symbol, spot=spot, expiry=expiry_date, dte=dte,
                         calls=calls, puts=puts)
        _meta_cache.set(cache_key, oc)
        logger.info("fetched option chain for %s exp=%s (%d calls, %d puts)",
                    symbol, expiry_date, len(calls), len(puts))
        return oc

    @staticmethod
    def _pick_expiry(expiries: list[str], target_dte: int) -> tuple[str, date, int]:
        today = date.today()
        dated = []
        for e in expiries:
            try:
                y, m, d = (int(x) for x in e.split("-"))
            except ValueError:
                continue
            exp = date(y, m, d)
            dted = (exp - today).days
            if dted >= 1:
                dated.append((e, exp, dted))
        if not dated:
            raise DataSourceError("no future option expirations")
        return min(dated, key=lambda x: abs(x[2] - target_dte))

    @staticmethod
    def _spot(ticker) -> float:
        try:
            fi = ticker.fast_info
            price = _f(getattr(fi, "last_price", None))
            if price:
                return price
        except Exception:  # noqa: BLE001 - fall back to history
            pass
        hist = ticker.history(period="5d")
        if hist is None or hist.empty:
            raise DataSourceError("no spot price for option underlying")
        return float(hist["Close"].iloc[-1])

    @staticmethod
    def _contracts(df, underlying: str, opt_type: str, expiry: date, dte: int):
        out: list[OptionContract] = []
        if df is None or getattr(df, "empty", True):
            return out
        for _, row in df.iterrows():
            bid, ask, last = _f(row.get("bid")), _f(row.get("ask")), _f(row.get("lastPrice"))
            if bid and ask and bid > 0 and ask > 0:
                premium = (bid + ask) / 2
            else:
                premium = last or 0.0
            if not premium or premium <= 0:
                continue
            vol, oi = _f(row.get("volume")), _f(row.get("openInterest"))
            out.append(OptionContract(
                contract_symbol=str(row.get("contractSymbol") or ""),
                underlying=underlying, opt_type=opt_type, strike=float(row["strike"]),
                expiry=expiry, dte=dte, premium=round(premium, 4),
                bid=bid, ask=ask, implied_volatility=_f(row.get("impliedVolatility")),
                volume=int(vol) if vol is not None else None,
                open_interest=int(oi) if oi is not None else None,
            ))
        return out
