"""Unit tests for backtest metrics + engine against known inputs."""
from __future__ import annotations

import math

import pytest

from app.services.backtesting import metrics as M
from app.services.backtesting.engine import run_backtest


def test_total_and_annualized_return():
    assert M.total_return([100, 110]) == pytest.approx(0.10)
    # Doubling over exactly one year (252 bars of equal growth).
    eq = [100 * (2 ** (1 / 252)) ** i for i in range(253)]
    assert M.annualized_return(eq) == pytest.approx(1.0, abs=1e-6)


def test_max_drawdown():
    assert M.max_drawdown([100, 120, 90, 130]) == pytest.approx(-0.25)
    assert M.max_drawdown([100, 101, 102]) == pytest.approx(0.0)


def test_win_rate_and_profit_factor():
    trades = [0.10, -0.05, 0.20]
    assert M.win_rate(trades) == pytest.approx(2 / 3)
    assert M.profit_factor(trades) == pytest.approx((0.10 + 0.20) / 0.05)
    assert M.average_trade_return(trades) == pytest.approx(0.25 / 3)


def test_sharpe_zero_when_flat():
    assert M.sharpe_ratio([0.0, 0.0, 0.0]) == 0.0
    # Positive constant returns -> zero dispersion -> sharpe 0 (guarded).
    assert M.sharpe_ratio([0.01, 0.01, 0.01]) == 0.0


def test_sortino_only_penalizes_downside():
    s = M.sortino_ratio([0.02, -0.01, 0.03, -0.02])
    assert math.isfinite(s)


def test_engine_buy_and_hold_matches_price_ratio():
    dates = ["2025-01-01", "2025-01-02", "2025-01-03", "2025-01-04"]
    closes = [100.0, 110.0, 121.0, 133.1]  # +10%/day
    positions = [1, 1, 1, 1]
    bench = [100.0, 100.0, 100.0, 100.0]
    res = run_backtest(dates, closes, positions, bench)
    # Buy & hold total return == price total return.
    assert res["metrics"]["total_return"] == pytest.approx(0.331, abs=1e-3)
    assert res["metrics"]["num_trades"] == 1  # one open trade, closed at end
    assert res["metrics"]["benchmark_total_return"] == pytest.approx(0.0)


def test_engine_flat_strategy_earns_nothing():
    dates = ["d1", "d2", "d3"]
    closes = [100.0, 200.0, 50.0]
    positions = [0, 0, 0]  # never invested
    res = run_backtest(dates, closes, positions, [100.0, 100.0, 100.0])
    assert res["metrics"]["total_return"] == pytest.approx(0.0)
    assert res["metrics"]["num_trades"] == 0
