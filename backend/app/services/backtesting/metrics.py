"""Performance & risk metrics — pure, deterministic functions.

The numbers an interviewer will scrutinize, so each is a small pure function with
known closed-form behavior and unit tests (docs/07-roadmap.md Phase 5). All take
plain sequences and return floats; no I/O, no global state.

Conventions: daily periodicity, 252 trading days/year, risk-free rate 0 unless
provided. Returns are simple (not log) returns.
"""
from __future__ import annotations

import math

TRADING_DAYS = 252


def total_return(equity: list[float]) -> float:
    if len(equity) < 2 or equity[0] == 0:
        return 0.0
    return equity[-1] / equity[0] - 1.0


def annualized_return(equity: list[float], periods_per_year: int = TRADING_DAYS) -> float:
    n = len(equity) - 1
    if n <= 0 or equity[0] <= 0 or equity[-1] <= 0:
        return 0.0
    return (equity[-1] / equity[0]) ** (periods_per_year / n) - 1.0


def daily_returns(equity: list[float]) -> list[float]:
    return [
        equity[i] / equity[i - 1] - 1.0
        for i in range(1, len(equity))
        if equity[i - 1] != 0
    ]


def _std(xs: list[float], mean: float) -> float:
    if len(xs) < 2:
        return 0.0
    var = sum((x - mean) ** 2 for x in xs) / (len(xs) - 1)
    return math.sqrt(var)


def sharpe_ratio(returns: list[float], rf: float = 0.0,
                 periods_per_year: int = TRADING_DAYS) -> float:
    """Annualized Sharpe. 0 when there's no dispersion (avoids div-by-zero)."""
    if len(returns) < 2:
        return 0.0
    excess = [r - rf / periods_per_year for r in returns]
    mean = sum(excess) / len(excess)
    std = _std(excess, mean)
    if std == 0:
        return 0.0
    return mean / std * math.sqrt(periods_per_year)


def sortino_ratio(returns: list[float], rf: float = 0.0,
                  periods_per_year: int = TRADING_DAYS) -> float:
    """Annualized Sortino (downside deviation in the denominator)."""
    if len(returns) < 2:
        return 0.0
    excess = [r - rf / periods_per_year for r in returns]
    mean = sum(excess) / len(excess)
    downside = [min(0.0, r) for r in excess]
    dd = math.sqrt(sum(d * d for d in downside) / len(excess))
    if dd == 0:
        return 0.0
    return mean / dd * math.sqrt(periods_per_year)


def max_drawdown(equity: list[float]) -> float:
    """Largest peak-to-trough decline as a negative fraction (e.g. -0.25)."""
    if not equity:
        return 0.0
    peak = equity[0]
    worst = 0.0
    for v in equity:
        peak = max(peak, v)
        if peak > 0:
            worst = min(worst, v / peak - 1.0)
    return worst


def win_rate(trade_returns: list[float]) -> float:
    if not trade_returns:
        return 0.0
    wins = sum(1 for r in trade_returns if r > 0)
    return wins / len(trade_returns)


def profit_factor(trade_returns: list[float]) -> float:
    """Gross gains / gross losses. inf-safe: returns 0 with no losses and no gains."""
    gains = sum(r for r in trade_returns if r > 0)
    losses = -sum(r for r in trade_returns if r < 0)
    if losses == 0:
        return float(gains > 0) * 999.0  # capped sentinel for "no losing trades"
    return gains / losses


def average_trade_return(trade_returns: list[float]) -> float:
    return sum(trade_returns) / len(trade_returns) if trade_returns else 0.0
