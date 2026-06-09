"""Alpaca options data adapter (per-user keys).

Fetches option chains from Alpaca's market-data API using a user's own Alpaca
keys. Alpaca's free "indicative" options feed is 15-min delayed but works from
cloud IPs — unlike yfinance — and returns the whole chain in one call. Greeks are
still computed locally via Black-Scholes (docs/06-data-sources.md).

Built per-request from the logged-in user's stored credentials, so each user
queries their own Alpaca entitlement.
"""
from __future__ import annotations

from datetime import date, timedelta

from app.core.logging import get_logger
from app.services.cache import TTLCache
from app.services.data_sources.base import (
    DataSourceError,
    OptionChain,
    OptionContract,
)

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


def _parse_occ(occ: str) -> tuple[str, float, date] | None:
    """Parse an OCC option symbol like 'AAPL260710C00320000' -> (type, strike, expiry)."""
    if len(occ) < 15:
        return None
    try:
        strike = int(occ[-8:]) / 1000.0
        cp = occ[-9]
        yymmdd = occ[-15:-9]
        opt_type = "call" if cp == "C" else "put" if cp == "P" else None
        if opt_type is None:
            return None
        expiry = date(2000 + int(yymmdd[:2]), int(yymmdd[2:4]), int(yymmdd[4:6]))
        return opt_type, strike, expiry
    except (ValueError, IndexError):
        return None


class AlpacaOptionsSource:
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
            hint = " (your Alpaca plan may not include options data)" if code in (401, 403) else ""
            raise DataSourceError(f"alpaca {path} returned HTTP {code}{hint}") from exc
        except Exception as exc:  # noqa: BLE001 - translate vendor/HTTP failure
            raise DataSourceError(f"alpaca request to {path} failed") from exc

    def _spot(self, symbol: str) -> float:
        data = self._get_json(f"/v2/stocks/{symbol}/trades/latest", {"feed": "iex"})
        price = _f((data.get("trade") or {}).get("p"))
        if not price:
            raise DataSourceError(f"no spot price for {symbol}")
        return price

    def get_option_chain(self, symbol: str, target_dte: int = 30) -> OptionChain:
        symbol = symbol.upper().strip()
        cache_key = f"alp-opt:{symbol}:{target_dte}"
        cached = _cache.get(cache_key)
        if cached is not None:
            return cached

        spot = self._spot(symbol)
        today = date.today()
        gte = (today + timedelta(days=max(1, target_dte - 18))).isoformat()
        lte = (today + timedelta(days=target_dte + 25)).isoformat()
        data = self._get_json(f"/v1beta1/options/snapshots/{symbol}", {
            "feed": "indicative", "limit": 1000,
            "expiration_date_gte": gte, "expiration_date_lte": lte,
            "strike_price_gte": round(spot * 0.8, 2),
            "strike_price_lte": round(spot * 1.2, 2),
        })

        by_expiry: dict[date, list[OptionContract]] = {}
        for occ, snap in (data.get("snapshots") or {}).items():
            parsed = _parse_occ(occ)
            if parsed is None:
                continue
            opt_type, strike, expiry = parsed
            quote = snap.get("latestQuote") or {}
            trade = snap.get("latestTrade") or {}
            bid, ask = _f(quote.get("bp")), _f(quote.get("ap"))
            if bid and ask and bid > 0 and ask > 0:
                premium = (bid + ask) / 2
            else:
                premium = _f(trade.get("p")) or 0.0
            if not premium or premium <= 0:
                continue
            contract = OptionContract(
                contract_symbol=occ, underlying=symbol, opt_type=opt_type, strike=strike,
                expiry=expiry, dte=(expiry - today).days, premium=round(premium, 4),
                bid=bid, ask=ask, implied_volatility=_f(snap.get("impliedVolatility")),
            )
            by_expiry.setdefault(expiry, []).append(contract)

        if not by_expiry:
            raise DataSourceError(f"no alpaca option contracts for {symbol}")
        chosen = min(by_expiry, key=lambda e: abs((e - today).days - target_dte))
        contracts = by_expiry[chosen]
        chain = OptionChain(
            underlying=symbol, spot=spot, expiry=chosen, dte=(chosen - today).days,
            calls=[c for c in contracts if c.opt_type == "call"],
            puts=[c for c in contracts if c.opt_type == "put"],
        )
        if not chain.calls and not chain.puts:
            raise DataSourceError(f"empty alpaca option chain for {symbol}")
        _cache.set(cache_key, chain)
        logger.info("alpaca option chain for %s exp=%s (%d calls, %d puts)",
                    symbol, chosen, len(chain.calls), len(chain.puts))
        return chain
