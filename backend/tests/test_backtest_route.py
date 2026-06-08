"""Runner + HTTP tests for backtesting (offline, fake price source)."""
from __future__ import annotations

from fastapi.testclient import TestClient

from app.db.session import get_db
from app.main import app
from app.models.user import User
from app.schemas.backtest import BacktestRequest
from app.services.backtesting.runner import BacktestError, run_and_store
from tests.fakes import FakeUptrendSource


def test_runner_produces_metrics_and_curve(db_session):
    user = User(email="bt@b.com", hashed_password="x")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    bt = run_and_store(
        db_session, user,
        BacktestRequest(strategy="sma_crossover", symbol="AAPL", benchmark="SPY",
                        horizon="1Y"),
        price_source=FakeUptrendSource(),
    )
    assert bt.symbol == "AAPL"
    assert "total_return" in bt.metrics and "sharpe" in bt.metrics
    assert len(bt.equity_curve) > 1
    assert bt.start_date < bt.end_date


def test_runner_rejects_unknown_strategy(db_session):
    user = User(email="bt2@b.com", hashed_password="x")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    try:
        run_and_store(db_session, user, BacktestRequest(strategy="bogus"),
                      price_source=FakeUptrendSource())
        raise AssertionError("expected BacktestError")
    except BacktestError:
        pass


def _auth(db_session, monkeypatch):
    monkeypatch.setattr("app.api.routes.backtest.get_price_source", FakeUptrendSource)
    app.dependency_overrides[get_db] = lambda: db_session
    client = TestClient(app)
    client.post("/auth/register", json={"email": "u@b.com", "password": "password123"})
    token = client.post(
        "/auth/login", json={"email": "u@b.com", "password": "password123"}
    ).json()["access_token"]
    return client, {"Authorization": f"Bearer {token}"}


def test_backtest_http_flow(db_session, monkeypatch):
    try:
        client, headers = _auth(db_session, monkeypatch)
        r = client.post(
            "/backtests",
            json={"strategy": "macd_trend", "symbol": "AAPL", "benchmark": "SPY",
                  "horizon": "1Y"},
            headers=headers,
        )
        assert r.status_code == 201
        body = r.json()
        assert body["strategy_label"] == "MACD Trend"
        assert body["metrics"]["num_trades"] >= 0
        assert len(body["equity_curve"]) > 1
        bid = body["id"]

        assert len(client.get("/backtests", headers=headers).json()) == 1
        assert client.get(f"/backtests/{bid}", headers=headers).json()["id"] == bid

        cmp = client.post("/backtests/compare", json={"backtest_ids": [bid]},
                          headers=headers)
        assert cmp.status_code == 200
        assert cmp.json()["items"][0]["id"] == bid
    finally:
        app.dependency_overrides.clear()


def test_backtests_require_auth(db_session):
    try:
        app.dependency_overrides[get_db] = lambda: db_session
        client = TestClient(app)
        assert client.get("/backtests").status_code == 401
    finally:
        app.dependency_overrides.clear()
