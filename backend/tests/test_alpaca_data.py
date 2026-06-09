"""Tests for the Alpaca market-data adapters (price bars + options chain).

The HTTP layer (`_get_json`) is monkeypatched so these run offline and assert the
parsing/normalization logic — OCC symbol parsing, bar coercion, expiry selection.
"""
from __future__ import annotations

from datetime import date, timedelta

import pytest

from app.services.data_sources.alpaca_options_source import (
    AlpacaOptionsSource,
    _parse_occ,
)
from app.services.data_sources.alpaca_price_source import AlpacaPriceSource
from app.services.data_sources.base import DataSourceError

_TODAY = date.today()
_EXP = _TODAY + timedelta(days=30)


def _occ(opt_type: str, strike: float) -> str:
    cp = "C" if opt_type == "call" else "P"
    yymmdd = _EXP.strftime("%y%m%d")
    return f"AAPL{yymmdd}{cp}{int(round(strike * 1000)):08d}"


# ---- OCC symbol parsing ----

def test_parse_occ_roundtrip():
    parsed = _parse_occ("AAPL260710C00320000")
    assert parsed is not None
    opt_type, strike, expiry = parsed
    assert opt_type == "call"
    assert strike == 320.0
    assert expiry == date(2026, 7, 10)


def test_parse_occ_put_and_garbage():
    assert _parse_occ(_occ("put", 285))[0] == "put"
    assert _parse_occ("TOOSHORT") is None
    assert _parse_occ("AAPL260710X00320000") is None  # not C/P


# ---- Options chain ----

def _fake_options_get_json(self, path, params):
    if "/trades/latest" in path:
        return {"trade": {"p": 300.0}}
    if "/options/snapshots/" in path:
        snaps = {}
        for s in (280, 290, 300, 310, 320):
            snaps[_occ("call", s)] = {
                "latestQuote": {"bp": 4.9, "ap": 5.1},
                "latestTrade": {"p": 5.0},
                "impliedVolatility": 0.30,
            }
            snaps[_occ("put", s)] = {
                "latestQuote": {"bp": 3.9, "ap": 4.1},
                "latestTrade": {"p": 4.0},
            }
        return {"snapshots": snaps}
    return {}


def test_alpaca_chain_parses(monkeypatch):
    monkeypatch.setattr(AlpacaOptionsSource, "_get_json", _fake_options_get_json)
    chain = AlpacaOptionsSource("k", "s").get_option_chain("AAPL", target_dte=30)
    assert chain.spot == 300.0
    assert chain.expiry == _EXP
    assert len(chain.calls) == 5 and len(chain.puts) == 5
    call = next(c for c in chain.calls if c.strike == 300.0)
    assert call.premium == 5.0  # (4.9 + 5.1) / 2
    assert call.implied_volatility == 0.30
    assert call.contract_symbol == _occ("call", 300)


def test_alpaca_chain_empty_raises(monkeypatch):
    def fake(self, path, params):
        if "/trades/latest" in path:
            return {"trade": {"p": 300.0}}
        return {"snapshots": {}}

    monkeypatch.setattr(AlpacaOptionsSource, "_get_json", fake)
    with pytest.raises(DataSourceError):
        AlpacaOptionsSource("k", "s").get_option_chain("ZZZ")


# ---- Price bars ----

def _fake_bars_get_json(self, path, params):
    assert params["feed"] == "iex"
    return {
        "bars": [
            {"t": "2024-06-05T04:00:00Z", "o": 1, "h": 2, "l": 0.5, "c": 1.5, "v": 100},
            {"t": "2024-06-06T04:00:00Z", "o": 1.5, "h": 2.5, "l": 1, "c": 2.0, "v": 200},
        ],
        "next_page_token": None,
    }


def test_alpaca_bars_parse_and_sort(monkeypatch):
    monkeypatch.setattr(AlpacaPriceSource, "_get_json", _fake_bars_get_json)
    bars = AlpacaPriceSource("k", "s").get_daily_bars("AAPL", lookback_days=365)
    assert len(bars) == 2
    assert bars[0].day == date(2024, 6, 5)
    assert bars[1].close == 2.0
    assert [b.day for b in bars] == sorted(b.day for b in bars)


def test_alpaca_bars_empty_raises(monkeypatch):
    monkeypatch.setattr(
        AlpacaPriceSource, "_get_json",
        lambda self, path, params: {"bars": [], "next_page_token": None},
    )
    with pytest.raises(DataSourceError):
        AlpacaPriceSource("k", "s").get_daily_bars("ZZZ")
