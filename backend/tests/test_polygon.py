"""Tests for the Polygon options adapter (HTTP layer mocked)."""
from __future__ import annotations

from datetime import date, timedelta

import pytest

from app.agents.options import run_options_agent
from app.services.data_sources.polygon_source import PolygonOptionsSource

_TODAY = date.today()
_EXP_NEAR = (_TODAY + timedelta(days=30)).isoformat()
_EXP_FAR = (_TODAY + timedelta(days=60)).isoformat()


def _contract(opt_type: str, strike: float) -> dict:
    cp = "C" if opt_type == "call" else "P"
    return {
        "details": {"contract_type": opt_type, "strike_price": strike,
                    "ticker": f"O:AAPL{cp}{int(strike)}", "expiration_date": _EXP_NEAR},
        "last_quote": {"bid": 4.9, "ask": 5.1},
        "implied_volatility": 0.30,
        "open_interest": 1500,
        "day": {"close": 5.0, "volume": 800},
    }


def _fake_get_json(self, path, params):
    if "/prev" in path:
        return {"results": [{"c": 300.0}]}
    if "/reference/options/contracts" in path:
        return {"results": [{"expiration_date": _EXP_NEAR}, {"expiration_date": _EXP_FAR}]}
    if "/snapshot/options/" in path:
        return {"results": [
            *[_contract("call", s) for s in (300, 310, 315, 320)],
            *[_contract("put", s) for s in (280, 285, 290, 300)],
        ]}
    return {"results": []}


def test_polygon_chain_parses(monkeypatch):
    monkeypatch.setattr(PolygonOptionsSource, "_get_json", _fake_get_json)
    chain = PolygonOptionsSource().get_option_chain("AAPL", target_dte=30)
    assert chain.spot == 300.0
    assert chain.expiry.isoformat() == _EXP_NEAR  # nearest to 30 DTE
    assert len(chain.calls) == 4 and len(chain.puts) == 4
    c = chain.calls[0]
    assert c.premium == 5.0  # (4.9 + 5.1) / 2
    assert c.implied_volatility == 0.30
    assert c.contract_symbol.startswith("O:AAPL")


def test_options_agent_uses_polygon_chain(monkeypatch):
    monkeypatch.setattr(PolygonOptionsSource, "_get_json", _fake_get_json)
    chain = PolygonOptionsSource().get_option_chain("AAPL", target_dte=30)
    out = run_options_agent("AAPL", chain, bullish=True, strength=75)
    assert out.vote.action == "Buy Call"
    assert out.strike_recommendation == 315  # ~5% OTM of 300
    assert out.greeks["delta"] > 0


def test_polygon_requires_key(monkeypatch):
    def boom(self, path, params):
        from app.services.data_sources.base import DataSourceError
        raise DataSourceError("Polygon API key not configured")

    monkeypatch.setattr(PolygonOptionsSource, "_get_json", boom)
    from app.services.data_sources.base import DataSourceError
    with pytest.raises(DataSourceError):
        PolygonOptionsSource().get_option_chain("ZZZ")
