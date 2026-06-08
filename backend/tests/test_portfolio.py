"""Service-level tests for portfolio accounting and the accept-recommendation loop."""
from __future__ import annotations

from decimal import Decimal

import pytest

from app.models.recommendation import Recommendation
from app.models.user import User
from app.services import portfolio as svc
from app.services.execution.simulated import SimulatedExecution
from tests.fakes import FakeUptrendSource


def _user(db) -> User:
    u = User(email="u@b.com", hashed_password="x")
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


def _rec(db, symbol="TEST", action="Buy", entry=100.0) -> Recommendation:
    rec = Recommendation(
        symbol=symbol, asset_type="stock", action=action,
        entry_target=Decimal(str(entry)), confidence=Decimal("70"),
        thesis="t", reasoning_report="r",
    )
    db.add(rec)
    db.commit()
    db.refresh(rec)
    return rec


def _accept(db, pf, rec, qty=None):
    ps = FakeUptrendSource()
    return svc.accept_recommendation(db, pf, rec.id, qty, None, ps, SimulatedExecution(ps))


def test_create_portfolio_sets_cash(db_session):
    pf = svc.create_portfolio(db_session, _user(db_session), "Main", 100_000)
    assert float(pf.cash_balance) == 100_000
    assert float(pf.starting_cash) == 100_000


def test_buy_updates_position_and_cash(db_session):
    user = _user(db_session)
    pf = svc.create_portfolio(db_session, user, "Main", 100_000)
    rec = _rec(db_session, action="Buy", entry=100.0)
    trade = _accept(db_session, pf, rec, qty=10)

    assert trade.side == "buy"
    assert float(trade.quantity) == 10 and float(trade.price) == 100
    assert float(pf.cash_balance) == 99_000
    pos = pf.positions[0]
    assert pos.symbol == "TEST" and float(pos.quantity) == 10 and float(pos.avg_cost) == 100


def test_accept_is_idempotent(db_session):
    user = _user(db_session)
    pf = svc.create_portfolio(db_session, user, "Main", 100_000)
    rec = _rec(db_session, entry=100.0)
    t1 = _accept(db_session, pf, rec, qty=10)
    t2 = _accept(db_session, pf, rec, qty=10)  # same recommendation again
    assert t1.id == t2.id
    assert float(pf.cash_balance) == 99_000  # not double-charged
    assert len(pf.trades) == 1


def test_buy_then_partial_sell(db_session):
    user = _user(db_session)
    pf = svc.create_portfolio(db_session, user, "Main", 100_000)
    _accept(db_session, pf, _rec(db_session, action="Buy", entry=100.0), qty=10)
    _accept(db_session, pf, _rec(db_session, action="Sell", entry=110.0), qty=4)

    assert float(pf.cash_balance) == 99_000 + 4 * 110
    assert float(pf.positions[0].quantity) == 6


def test_sell_entire_position_removes_it(db_session):
    user = _user(db_session)
    pf = svc.create_portfolio(db_session, user, "Main", 100_000)
    _accept(db_session, pf, _rec(db_session, action="Buy", entry=100.0), qty=10)
    _accept(db_session, pf, _rec(db_session, action="Sell", entry=120.0), qty=10)
    assert pf.positions == []


def test_hold_action_is_rejected(db_session):
    user = _user(db_session)
    pf = svc.create_portfolio(db_session, user, "Main", 100_000)
    rec = _rec(db_session, action="Hold")
    with pytest.raises(svc.TradeRejected):
        _accept(db_session, pf, rec, qty=1)


def test_insufficient_cash_rejected(db_session):
    user = _user(db_session)
    pf = svc.create_portfolio(db_session, user, "Small", 50)
    rec = _rec(db_session, action="Buy", entry=100.0)
    with pytest.raises(svc.TradeRejected):
        _accept(db_session, pf, rec)  # one share costs 100, only 50 cash


def test_summary_and_review(db_session):
    user = _user(db_session)
    pf = svc.create_portfolio(db_session, user, "Main", 100_000)
    _accept(db_session, pf, _rec(db_session, action="Buy", entry=100.0), qty=10)

    summary = svc.summarize(db_session, pf, FakeUptrendSource())
    assert summary.num_positions == 1
    assert summary.total_value > 100_000  # FakeUptrend marks above cost
    assert "risk_score" in summary.risk

    review = svc.review_holdings(db_session, pf, FakeUptrendSource())
    assert len(review.reviews) == 1
    assert review.reviews[0].symbol == "TEST"
    assert review.reviews[0].action in {"Hold", "Add", "Trim", "Sell", "Hedge"}

    alloc = svc.allocation(pf)
    assert alloc.by_symbol[0].label == "TEST"
    assert alloc.by_symbol[0].pct == 100.0


def test_buy_call_option_uses_100_multiplier(db_session):
    user = _user(db_session)
    pf = svc.create_portfolio(db_session, user, "Main", 100_000)
    rec = Recommendation(
        symbol="NVDA250215C00185000", asset_type="option", action="Buy Call",
        entry_target=Decimal("5.0"), confidence=Decimal("60"), thesis="t",
        reasoning_report="r",
    )
    db_session.add(rec)
    db_session.commit()
    db_session.refresh(rec)

    trade = _accept(db_session, pf, rec, qty=2)
    assert trade.side == "buy" and float(trade.quantity) == 2
    # 2 contracts * $5 premium * 100 multiplier = $1,000.
    assert float(pf.cash_balance) == 99_000
    pos = pf.positions[0]
    assert pos.asset_type == "option" and float(pos.quantity) == 2
    out = svc.positions_out(pf)[0]
    assert out.market_value == 1000.0  # premium * 100 * contracts


def test_ownership_enforced(db_session):
    owner = _user(db_session)
    pf = svc.create_portfolio(db_session, owner, "Main", 100_000)
    other = User(email="other@b.com", hashed_password="x")
    db_session.add(other)
    db_session.commit()
    db_session.refresh(other)
    with pytest.raises(svc.Forbidden):
        svc.get_owned_portfolio(db_session, other, pf.id)
