"""Tests for the Finnhub adapters + the fundamentals/news fallback chain."""
from __future__ import annotations

import pytest

from app.services.data_sources import finnhub_source as fh
from app.services.data_sources.base import DataSourceError
from app.services.data_sources.chained import (
    ChainedFundamentalsSource,
    ChainedNewsSource,
)


class FakeFinnhubClient:
    def company_basic_financials(self, symbol, kind):
        return {"metric": {
            "peTTM": 24.5, "pbQuarterly": 6.1, "netProfitMarginTTM": 25.3,
            "revenueGrowthTTMYoy": 8.0, "epsGrowthTTMYoy": 12.0, "roeTTM": 30.0,
            "totalDebt/totalEquityQuarterly": 1.5,
        }}

    def company_profile2(self, symbol):
        return {"name": "Apple Inc", "finnhubIndustry": "Technology",
                "marketCapitalization": 3_000_000}  # millions

    def company_news(self, symbol, _from, to):
        return [
            {"headline": "Company beats earnings", "source": "Reuters",
             "datetime": 1_700_000_000},
            {"headline": "Analysts upgrade outlook", "source": "Bloomberg",
             "datetime": 1_700_100_000},
        ]

    def recommendation_trends(self, symbol):
        return [{"period": "2025-01-01", "strongBuy": 8, "buy": 12, "hold": 4,
                 "sell": 1, "strongSell": 0}]

    def symbol_lookup(self, query):
        rows = {
            "SPY": {"symbol": "SPY", "type": "ETP", "description": "SPDR S&P 500 ETF"},
            "AAPL": {"symbol": "AAPL", "type": "Common Stock", "description": "Apple"},
        }
        match = rows.get(query.upper())
        return {"count": 1, "result": [match]} if match else {"result": []}


def test_finnhub_fundamentals_mapping(monkeypatch):
    monkeypatch.setattr(fh, "make_client", lambda: FakeFinnhubClient())
    f = fh.FinnhubFundamentalsSource().get_fundamentals("AAPL")
    assert f.pe == 24.5 and f.pb == 6.1
    assert f.profit_margin == pytest.approx(0.253)  # percent -> fraction
    assert f.roe == pytest.approx(0.30)
    assert f.debt_to_equity == pytest.approx(150.0)  # ratio 1.5 -> 150 (yfinance scale)
    assert f.market_cap == pytest.approx(3e12)  # millions -> absolute
    assert f.sector == "Technology"


def test_finnhub_news_and_analysts(monkeypatch):
    monkeypatch.setattr(fh, "make_client", lambda: FakeFinnhubClient())
    data = fh.FinnhubNewsSource().get_sentiment_data("AAPL")
    assert len(data.news) == 2
    assert data.news[0].publisher == "Reuters"
    assert data.analysts.strong_buy == 8 and data.analysts.total == 25


def test_finnhub_requires_key(monkeypatch):
    # make_client raises when no key configured.
    def no_key():
        raise DataSourceError("Finnhub API key not configured")

    monkeypatch.setattr(fh, "make_client", no_key)
    with pytest.raises(DataSourceError):
        fh.FinnhubFundamentalsSource().get_fundamentals("ZZZ")  # uncached symbol


def test_classify_symbol_detects_etf_vs_stock(monkeypatch):
    monkeypatch.setattr(fh, "make_client", lambda: FakeFinnhubClient())
    fh._class_cache.clear()
    assert fh.classify_symbol("SPY") == "etf"   # type "ETP"
    assert fh.classify_symbol("AAPL") == "stock"  # type "Common Stock"
    assert fh.classify_symbol("ZZZZ") is None     # no match -> undetermined


def test_classify_symbol_none_without_key(monkeypatch):
    def no_key():
        raise DataSourceError("Finnhub API key not configured")

    monkeypatch.setattr(fh, "make_client", no_key)
    fh._class_cache.clear()
    assert fh.classify_symbol("SPY") is None


def test_chain_falls_back_to_second_source():
    class Failing:
        def get_fundamentals(self, symbol):
            raise DataSourceError("down")

    class Working:
        def get_fundamentals(self, symbol):
            from app.services.data_sources.base import Fundamentals
            return Fundamentals(symbol=symbol, pe=15)

    chained = ChainedFundamentalsSource([Failing(), Working()])
    assert chained.get_fundamentals("X").pe == 15


def test_chain_raises_when_all_fail():
    class Failing:
        def get_sentiment_data(self, symbol, limit=20):
            raise DataSourceError("down")

    with pytest.raises(DataSourceError):
        ChainedNewsSource([Failing(), Failing()]).get_sentiment_data("X")
