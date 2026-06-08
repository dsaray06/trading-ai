"""Unit tests for the Fundamental agent's deterministic scoring."""
from __future__ import annotations

from app.agents.fundamental import run_fundamental_agent, score_fundamentals
from app.services.data_sources.base import Fundamentals


def test_cheap_high_quality_scores_bullish_and_buys():
    f = Fundamentals(
        symbol="X", pe=12, pb=1.2, profit_margin=0.30, roe=0.28,
        revenue_growth=0.22, earnings_growth=0.30, debt_to_equity=30,
    )
    s = score_fundamentals(f)
    assert s.valuation > 80
    assert s.quality > 90
    assert s.composite > 70
    assert run_fundamental_agent("X", f).vote.action == "Buy"


def test_expensive_weak_scores_bearish_and_sells():
    f = Fundamentals(
        symbol="Y", pe=80, pb=15, profit_margin=-0.05, roe=-0.10,
        revenue_growth=-0.10, earnings_growth=-0.20, debt_to_equity=300,
    )
    s = score_fundamentals(f)
    assert s.valuation < 10
    assert s.composite < 30
    assert run_fundamental_agent("Y", f).vote.action == "Sell"


def test_missing_metrics_are_skipped_not_counted_as_zero():
    f = Fundamentals(symbol="Z", pe=15)  # only one metric
    s = score_fundamentals(f)
    assert s.quality is None and s.growth is None and s.financial_health is None
    assert s.composite is not None  # valuation alone still yields a composite


def test_no_metrics_abstains():
    out = run_fundamental_agent("Z", Fundamentals(symbol="Z"))
    assert out.vote.abstain is True


def test_scores_bounded():
    f = Fundamentals(symbol="B", pe=1, pb=0.1, profit_margin=2.0, roe=2.0,
                     revenue_growth=2.0, earnings_growth=2.0, debt_to_equity=-5)
    s = score_fundamentals(f)
    assert 0 <= s.composite <= 100
    assert 0 <= s.valuation <= 100
