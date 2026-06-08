"""Integration test for the multi-agent research slice (offline, fake sources)."""
from __future__ import annotations

from fastapi.testclient import TestClient

from app.db.session import get_db
from app.main import app
from app.models.recommendation import Recommendation
from app.services.research import ResearchRequest, run_research
from tests.fakes import (
    FakeFundamentalsSource,
    FakeNewsSource,
    FakeOptionsSource,
    FakeUptrendSource,
)


def _fakes() -> dict:
    return dict(
        price_source=FakeUptrendSource(),
        fundamentals_source=FakeFundamentalsSource(),
        news_source=FakeNewsSource(),
        options_source=FakeOptionsSource(),
    )


def test_run_research_persists_votes_and_explains(db_session):
    resp = run_research(db_session, "test", ResearchRequest(), **_fakes())

    assert resp.ticker == "TEST"
    assert resp.action in {"Buy", "Add", "Hold", "Trim", "Sell"}
    assert 0 <= resp.confidence <= 100
    assert resp.disclaimer.startswith("Research")

    agents = {v.agent for v in resp.agent_votes}
    assert agents == {"market", "fundamental", "sentiment", "options"}
    # Options abstains for an equity request.
    options_vote = next(v for v in resp.agent_votes if v.agent == "options")
    assert options_vote.weight == 0.0
    assert resp.reasoning_report  # decision report (template fallback w/o LLM key)
    assert {"technical", "fundamental", "sentiment"} <= set(resp.analysis.keys())

    rows = db_session.query(Recommendation).all()
    assert len(rows) == 1
    assert len(rows[0].votes) == 4


def test_options_request_yields_call(db_session):
    resp = run_research(db_session, "NVDA", ResearchRequest(include_options=True), **_fakes())
    assert resp.action == "Buy Call"
    assert resp.asset_type == "option"
    assert resp.entry_target == 5.0
    assert "options" in resp.analysis
    rec = db_session.query(Recommendation).one()
    assert rec.asset_type == "option"
    assert rec.symbol.startswith("NVDA")  # contract symbol, not the bare ticker


def test_bullish_inputs_lean_buy(db_session):
    resp = run_research(db_session, "UP", ResearchRequest(), **_fakes())
    assert resp.action in {"Buy", "Add"}


def test_research_route_returns_recommendation(db_session, monkeypatch):
    # Route uses default yfinance sources; swap all of them for fakes (no network).
    monkeypatch.setattr("app.services.research.YFinancePriceSource", FakeUptrendSource)
    monkeypatch.setattr(
        "app.services.research.YFinanceFundamentalsSource", FakeFundamentalsSource
    )
    monkeypatch.setattr("app.services.research.YFinanceNewsSource", FakeNewsSource)
    monkeypatch.setattr("app.services.research.YFinanceOptionsSource", FakeOptionsSource)
    app.dependency_overrides[get_db] = lambda: db_session
    try:
        client = TestClient(app)
        r = client.post("/research/AAPL", json={"asset_type": "stock"})
        assert r.status_code == 200
        body = r.json()
        assert body["ticker"] == "AAPL"
        assert len(body["agent_votes"]) == 4
        assert body["disclaimer"].startswith("Research")
    finally:
        app.dependency_overrides.clear()


def test_health_endpoint():
    client = TestClient(app)
    assert client.get("/health").json() == {"status": "ok"}
