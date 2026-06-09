"""Polygon options adapter.

Provides option chains via Polygon's REST API (keyed, works from cloud IPs,
unlike yfinance's options endpoint). Requires `POLYGON_API_KEY`. We use the
reference endpoint to pick an expiration near the target DTE, then the chain
snapshot for that expiration (strike, premium, IV, OI). Greeks are still computed
locally via Black-Scholes (docs/06-data-sources.md).
"""
from __future__ import annotations

from datetime import date, timedelta

from app.core.config import get_settings
from app.core.logging import get_logger
from app.services.cache import TTLCache
from app.services.data_sources.base import (
    DataSourceError,
    OptionChain,
    OptionContract,
)

logger = get_logger(__name__)
_cache = TTLCache(ttl_seconds=900.0)
_BASE = "https://api.polygon.io"


def _f(value) -> float | None:
    if value is None:
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return None if out != out else out


def _parse_date(s: str) -> date:
    y, m, d = (int(x) for x in s.split("-"))
    return date(y, m, d)


class PolygonOptionsSource:
    def _get_json(self, path: str, params: dict) -> dict:
        """HTTP GET against Polygon (lazy httpx import). Monkeypatched in tests."""
        settings = get_settings()
        if not settings.polygon_api_key:
            raise DataSourceError("Polygon API key not configured")
        import httpx

        try:
            resp = httpx.get(
                f"{_BASE}{path}",
                params={**params, "apiKey": settings.polygon_api_key},
                timeout=20.0,
            )
            resp.raise_for_status()
            return resp.json()
        except Exception as exc:  # noqa: BLE001 - translate vendor/HTTP failure
            raise DataSourceError(f"polygon request failed ({path}): {exc}") from exc

    def _spot(self, symbol: str) -> float:
        data = self._get_json(f"/v2/aggs/ticker/{symbol}/prev", {"adjusted": "true"})
        results = data.get("results") or []
        if not results:
            raise DataSourceError(f"no spot price for {symbol}")
        return float(results[0]["c"])

    def _pick_expiration(self, symbol: str, target_dte: int) -> tuple[date, int]:
        today = date.today()
        data = self._get_json("/v3/reference/options/contracts", {
            "underlying_ticker": symbol,
            "expiration_date.gte": today.isoformat(),
            "expiration_date.lte": (today + timedelta(days=120)).isoformat(),
            "limit": 1000,
        })
        expiries = sorted({
            c["expiration_date"] for c in (data.get("results") or [])
            if c.get("expiration_date")
        })
        future = [(_parse_date(e), (_parse_date(e) - today).days) for e in expiries]
        future = [(e, dte) for e, dte in future if dte >= 1]
        if not future:
            raise DataSourceError(f"no future option expirations for {symbol}")
        return min(future, key=lambda x: abs(x[1] - target_dte))

    def get_option_chain(self, symbol: str, target_dte: int = 30) -> OptionChain:
        symbol = symbol.upper().strip()
        cache_key = f"poly-opt:{symbol}:{target_dte}"
        cached = _cache.get(cache_key)
        if cached is not None:
            return cached

        spot = self._spot(symbol)
        expiry, dte = self._pick_expiration(symbol, target_dte)
        snap = self._get_json(f"/v3/snapshot/options/{symbol}", {
            "expiration_date": expiry.isoformat(), "limit": 250,
        })

        calls: list[OptionContract] = []
        puts: list[OptionContract] = []
        for r in (snap.get("results") or []):
            details = r.get("details") or {}
            opt_type = details.get("contract_type")
            strike = _f(details.get("strike_price"))
            if strike is None or opt_type not in ("call", "put"):
                continue
            quote = r.get("last_quote") or {}
            trade = r.get("last_trade") or {}
            day = r.get("day") or {}
            bid, ask = _f(quote.get("bid")), _f(quote.get("ask"))
            if bid and ask and bid > 0 and ask > 0:
                premium = (bid + ask) / 2
            else:
                premium = _f(trade.get("price")) or _f(day.get("close")) or 0.0
            if not premium or premium <= 0:
                continue
            vol, oi = _f(day.get("volume")), _f(r.get("open_interest"))
            contract = OptionContract(
                contract_symbol=details.get("ticker", ""), underlying=symbol,
                opt_type=opt_type, strike=strike, expiry=expiry, dte=dte,
                premium=round(premium, 4), bid=bid, ask=ask,
                implied_volatility=_f(r.get("implied_volatility")),
                volume=int(vol) if vol is not None else None,
                open_interest=int(oi) if oi is not None else None,
            )
            (calls if opt_type == "call" else puts).append(contract)

        if not calls and not puts:
            raise DataSourceError(f"empty polygon option chain for {symbol}")
        chain = OptionChain(underlying=symbol, spot=spot, expiry=expiry, dte=dte,
                            calls=calls, puts=puts)
        _cache.set(cache_key, chain)
        logger.info("polygon option chain for %s exp=%s (%d calls, %d puts)",
                    symbol, expiry, len(calls), len(puts))
        return chain
