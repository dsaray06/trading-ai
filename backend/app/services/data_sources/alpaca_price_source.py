"""Alpaca daily-bar price adapter (per-user keys).

Fetches historical daily OHLCV bars from Alpaca's market-data API using a user's
own Alpaca keys. Alpaca's free IEX feed works from cloud IPs — unlike yfinance,
whose price endpoint is blocked from datacenter ranges — so this is what keeps the
Market agent alive in production. Built per-request from the logged-in user's
stored credentials (docs/06-data-sources.md).
"""
from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

from app.core.logging import get_logger
from app.services.cache import TTLCache
from app.services.data_sources.base import DataSourceError, PriceBar

logger = get_logger(__name__)
_cache = TTLCache(ttl_seconds=900.0)
_DATA_BASE = "https://data.alpaca.markets"


def _f(value) -> float | None:
    if value is None:
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return None if out != out else out


def _parse_day(ts: str) -> date | None:
    """Parse an Alpaca RFC-3339 bar timestamp like '2024-06-07T04:00:00Z' -> date."""
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00")).date()
    except (ValueError, AttributeError):
        return None


class AlpacaPriceSource:
    """Daily OHLCV bars from Alpaca, normalized to `PriceBar`."""

    def __init__(self, api_key: str, api_secret: str) -> None:
        self._key = api_key
        self._secret = api_secret

    def _get_json(self, path: str, params: dict) -> dict:
        """HTTP GET against Alpaca data API. Monkeypatched in tests."""
        import httpx

        headers = {"APCA-API-KEY-ID": self._key, "APCA-API-SECRET-KEY": self._secret}
        try:
            resp = httpx.get(f"{_DATA_BASE}{path}", params=params, headers=headers,
                             timeout=20.0)
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPStatusError as exc:
            code = exc.response.status_code
            hint = " (your Alpaca plan may not include this data)" if code in (401, 403) else ""
            raise DataSourceError(f"alpaca {path} returned HTTP {code}{hint}") from exc
        except Exception as exc:  # noqa: BLE001 - translate vendor/HTTP failure
            raise DataSourceError(f"alpaca request to {path} failed") from exc

    def get_daily_bars(self, symbol: str, lookback_days: int = 365) -> list[PriceBar]:
        symbol = symbol.upper().strip()
        cache_key = f"alp-bars:{symbol}:{lookback_days}"
        cached = _cache.get(cache_key)
        if cached is not None:
            return cached

        # Pad the window so we still get ~lookback_days of *trading* days, and end
        # one day back to stay inside the free feed's 15-min-delay entitlement.
        start = (datetime.now(UTC) - timedelta(days=lookback_days + 5)).date().isoformat()
        bars: list[PriceBar] = []
        page_token: str | None = None
        for _ in range(20):  # hard cap on pagination
            params = {"timeframe": "1Day", "start": start, "feed": "iex",
                      "limit": 10000, "adjustment": "all"}
            if page_token:
                params["page_token"] = page_token
            data = self._get_json(f"/v2/stocks/{symbol}/bars", params)
            for raw in data.get("bars") or []:
                day = _parse_day(raw.get("t"))
                o, h, l_, c, v = (_f(raw.get(k)) for k in ("o", "h", "l", "c", "v"))
                if day is None or None in (o, h, l_, c, v):
                    continue
                bars.append(PriceBar(day=day, open=o, high=h, low=l_, close=c, volume=v))
            page_token = data.get("next_page_token")
            if not page_token:
                break

        if not bars:
            raise DataSourceError(f"no alpaca price data for {symbol}")
        bars.sort(key=lambda b: b.day)
        _cache.set(cache_key, bars)
        logger.info("fetched %d alpaca daily bars for %s", len(bars), symbol)
        return bars
