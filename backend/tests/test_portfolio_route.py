"""HTTP test for the full auth + accept-recommendation loop."""
from __future__ import annotations

from decimal import Decimal

from fastapi.testclient import TestClient

from app.db.session import get_db
from app.main import app
from app.models.recommendation import Recommendation
from tests.fakes import FakeUptrendSource


def _auth_client(db_session, monkeypatch) -> tuple[TestClient, dict]:
    monkeypatch.setattr("app.api.routes.portfolio.get_price_source", FakeUptrendSource)
    app.dependency_overrides[get_db] = lambda: db_session
    client = TestClient(app)
    client.post("/auth/register", json={"email": "t@b.com", "password": "password123"})
    token = client.post(
        "/auth/login", json={"email": "t@b.com", "password": "password123"}
    ).json()["access_token"]
    return client, {"Authorization": f"Bearer {token}"}


def _make_rec(db_session, symbol="AAPL", action="Buy", entry=100.0) -> Recommendation:
    rec = Recommendation(
        symbol=symbol, asset_type="stock", action=action,
        entry_target=Decimal(str(entry)), confidence=Decimal("70"),
        thesis="t", reasoning_report="r",
    )
    db_session.add(rec)
    db_session.commit()
    db_session.refresh(rec)
    return rec


def test_full_accept_loop(db_session, monkeypatch):
    try:
        client, headers = _auth_client(db_session, monkeypatch)

        pf_id = client.post(
            "/portfolios", json={"name": "Main", "starting_cash": 100000}, headers=headers
        ).json()["id"]

        rec = _make_rec(db_session, "AAPL", "Buy", 100.0)
        r = client.post(
            f"/portfolios/{pf_id}/trades",
            json={"recommendation_id": str(rec.id), "quantity": 10},
            headers=headers,
        )
        assert r.status_code == 201
        trade = r.json()
        assert trade["side"] == "buy" and trade["quantity"] == 10

        summary = client.get(f"/portfolios/{pf_id}", headers=headers).json()
        assert summary["num_positions"] == 1
        assert summary["cash_balance"] == 99000

        positions = client.get(f"/portfolios/{pf_id}/positions", headers=headers).json()
        assert positions[0]["symbol"] == "AAPL" and positions[0]["quantity"] == 10

        # Idempotency over HTTP: re-accepting doesn't double the position.
        client.post(
            f"/portfolios/{pf_id}/trades",
            json={"recommendation_id": str(rec.id), "quantity": 10},
            headers=headers,
        )
        positions = client.get(f"/portfolios/{pf_id}/positions", headers=headers).json()
        assert positions[0]["quantity"] == 10
        trades = client.get(f"/portfolios/{pf_id}/trades", headers=headers).json()
        assert len(trades) == 1
    finally:
        app.dependency_overrides.clear()


def test_trade_preview_suggests_quantity(db_session, monkeypatch):
    try:
        client, headers = _auth_client(db_session, monkeypatch)
        pf_id = client.post(
            "/portfolios", json={"name": "Main", "starting_cash": 100000}, headers=headers
        ).json()["id"]
        rec = _make_rec(db_session, "AAPL", "Buy", 100.0)

        r = client.get(
            f"/portfolios/{pf_id}/trades/preview/{rec.id}", headers=headers
        )
        assert r.status_code == 200
        p = r.json()
        assert p["side"] == "buy" and p["symbol"] == "AAPL"
        # 2% risk on $100k at $100 w/ default 8% stop -> 25 shares, capped affordable.
        assert p["suggested_quantity"] > 0
        assert p["estimated_cost"] == p["suggested_quantity"] * 100.0
        assert 0 < p["pct_of_portfolio"] <= 100
        assert "share" in p["note"]
    finally:
        app.dependency_overrides.clear()


def test_portfolio_requires_auth(db_session, monkeypatch):
    try:
        app.dependency_overrides[get_db] = lambda: db_session
        client = TestClient(app)
        assert client.get("/portfolios").status_code == 401
    finally:
        app.dependency_overrides.clear()
