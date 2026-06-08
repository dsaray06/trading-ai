"""Tests for per-user Alpaca credentials and Alpaca-linked portfolios."""
from __future__ import annotations

from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app.db.session import get_db
from app.main import app
from app.models.recommendation import Recommendation
from app.models.user import User
from app.services import alpaca_credentials as creds
from app.services import portfolio as svc
from app.services.execution.base import BrokerPosition
from tests.fakes import FakeAlpacaBroker, FakeUptrendSource


def _user(db, email="alp@b.com") -> User:
    u = User(email=email, hashed_password="x")
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


def _rec(db, symbol="MSFT", action="Buy", entry=200.0, asset_type="stock"):
    rec = Recommendation(
        symbol=symbol, asset_type=asset_type, action=action,
        entry_target=Decimal(str(entry)), confidence=Decimal("60"),
        thesis="t", reasoning_report="r",
    )
    db.add(rec)
    db.commit()
    db.refresh(rec)
    return rec


# ---- credential service (mock the broker factory) -------------------------

def test_save_and_load_credential_roundtrip(db_session, monkeypatch):
    shared = FakeAlpacaBroker()
    monkeypatch.setattr(creds, "_build_broker", lambda k, s: shared)
    user = _user(db_session)

    assert creds.is_connected(db_session, user) is False
    creds.save_credential(db_session, user, "PKTESTKEY1234", "secretsecret123")
    assert creds.is_connected(db_session, user) is True

    cred = creds.get_credential(db_session, user)
    assert cred.api_key == "PKTESTKEY1234"
    # Secret is encrypted at rest, not stored in the clear.
    assert "secretsecret123" not in cred.secret_encrypted
    # ...but a broker can be rebuilt for the user.
    assert creds.broker_for_user(db_session, user) is shared


def test_save_invalid_credential_raises(db_session, monkeypatch):
    from app.services.execution.base import ExecutionError

    def boom(_k, _s):
        class Bad:
            def get_account(self):
                raise ExecutionError("401 unauthorized")
        return Bad()

    monkeypatch.setattr(creds, "_build_broker", boom)
    with pytest.raises(creds.CredentialError):
        creds.save_credential(db_session, _user(db_session), "BADKEY12", "BADSEC12")


def test_masked_key():
    assert creds.masked_key("PKABCDEFGH1234") == "PKAB…1234"


def test_broker_for_user_none_when_not_connected(db_session):
    assert creds.broker_for_user(db_session, _user(db_session)) is None


# ---- Alpaca-linked portfolio service (broker passed directly) -------------

def test_create_alpaca_portfolio_mirrors_account(db_session):
    broker = FakeAlpacaBroker(cash=75_000)
    broker._positions = [BrokerPosition("AAPL", 10, 150, 160, 1600, 100)]
    pf = svc.create_portfolio(db_session, _user(db_session), "Alpaca", 0,
                              broker="alpaca", alpaca_broker=broker)
    assert pf.broker == "alpaca"
    assert float(pf.cash_balance) == 75_000
    assert len(pf.positions) == 1 and pf.positions[0].symbol == "AAPL"


def test_accept_via_alpaca_submits_and_resyncs(db_session):
    broker = FakeAlpacaBroker(cash=100_000)
    pf = svc.create_portfolio(db_session, _user(db_session), "Alpaca", 0,
                              broker="alpaca", alpaca_broker=broker)
    rec = _rec(db_session, "MSFT", "Buy", 200.0)
    trade = svc.accept_recommendation(
        db_session, pf, rec.id, 5, None, FakeUptrendSource(), broker
    )
    assert trade.side == "buy" and broker.orders
    assert {p.symbol for p in pf.positions} == {"MSFT"}
    assert float(pf.cash_balance) == 100_000 - 5 * 200


def test_options_rejected_on_alpaca_portfolio(db_session):
    broker = FakeAlpacaBroker()
    pf = svc.create_portfolio(db_session, _user(db_session), "Alpaca", 0,
                              broker="alpaca", alpaca_broker=broker)
    rec = _rec(db_session, "NVDA250101C00100000", "Buy Call", 5.0, asset_type="option")
    with pytest.raises(svc.TradeRejected):
        svc.accept_recommendation(db_session, pf, rec.id, 1, None, FakeUptrendSource(),
                                  broker)


# ---- HTTP flows -----------------------------------------------------------

def test_config_reports_alpaca_available(db_session):
    app.dependency_overrides[get_db] = lambda: db_session
    try:
        body = TestClient(app).get("/config").json()
        assert body["alpaca_available"] is True
        assert "disclaimer" in body
    finally:
        app.dependency_overrides.clear()


def _auth_client(db_session):
    client = TestClient(app)
    client.post("/auth/register", json={"email": "h@b.com", "password": "password123"})
    token = client.post(
        "/auth/login", json={"email": "h@b.com", "password": "password123"}
    ).json()["access_token"]
    return client, {"Authorization": f"Bearer {token}"}


def test_connect_then_create_alpaca_portfolio_over_http(db_session, monkeypatch):
    shared = FakeAlpacaBroker(cash=50_000)
    monkeypatch.setattr(creds, "_build_broker", lambda k, s: shared)
    app.dependency_overrides[get_db] = lambda: db_session
    try:
        client, headers = _auth_client(db_session)

        # Not connected yet -> creating an Alpaca portfolio is rejected.
        assert client.get("/alpaca/credentials", headers=headers).json()["connected"] is False
        r = client.post("/portfolios", json={"name": "A", "broker": "alpaca"}, headers=headers)
        assert r.status_code == 422

        # Connect, then it works.
        conn = client.post("/alpaca/credentials",
                           json={"api_key": "PKTESTKEY1234", "api_secret": "secretsecret"},
                           headers=headers)
        assert conn.status_code == 200 and conn.json()["connected"] is True
        assert conn.json()["api_key_masked"] == "PKTE…1234"

        r = client.post("/portfolios", json={"name": "A", "broker": "alpaca"}, headers=headers)
        assert r.status_code == 201
        assert r.json()["broker"] == "alpaca"
        assert r.json()["cash_balance"] == 50_000

        # Disconnect.
        assert client.delete("/alpaca/credentials", headers=headers).json()["connected"] is False
    finally:
        app.dependency_overrides.clear()
