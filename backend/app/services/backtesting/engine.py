"""Backtest engine: replay positions over prices, compute equity + metrics.

Pure given its inputs (aligned dates/closes/positions/benchmark) — no I/O, fully
deterministic. No look-ahead: position[t] (decided from data through bar t) earns
the bar t→t+1 return, so future prices never influence a past decision.
"""
from __future__ import annotations

from app.services.backtesting import metrics as M

INITIAL_CAPITAL = 10_000.0
_MAX_CURVE_POINTS = 300


def _equity_from_positions(closes: list[float], positions: list[int],
                           initial: float) -> list[float]:
    equity = [initial]
    for t in range(len(closes) - 1):
        ret = closes[t + 1] / closes[t] - 1.0 if closes[t] else 0.0
        equity.append(equity[-1] * (1.0 + positions[t] * ret))
    return equity


def _benchmark_equity(bm_closes: list[float], initial: float) -> list[float]:
    base = bm_closes[0] if bm_closes and bm_closes[0] else 1.0
    return [initial * c / base for c in bm_closes]


def _round_trip_returns(closes: list[float], positions: list[int]) -> list[float]:
    """Per-trade returns from 0->1 entries to 1->0 exits (long-only)."""
    trades: list[float] = []
    entry: int | None = None
    for t, p in enumerate(positions):
        if p == 1 and entry is None:
            entry = t
        elif p == 0 and entry is not None:
            trades.append(closes[t] / closes[entry] - 1.0)
            entry = None
    if entry is not None:  # still open at the end -> close at last bar
        trades.append(closes[-1] / closes[entry] - 1.0)
    return trades


def _downsample(dates: list[str], strat: list[float], bench: list[float]) -> list[dict]:
    n = len(dates)
    step = max(1, n // _MAX_CURVE_POINTS)
    idx = list(range(0, n, step))
    if idx[-1] != n - 1:
        idx.append(n - 1)
    return [
        {"date": dates[i], "strategy": round(strat[i], 2), "benchmark": round(bench[i], 2)}
        for i in idx
    ]


def run_backtest(
    dates: list[str],
    closes: list[float],
    positions: list[int],
    benchmark_closes: list[float],
    initial: float = INITIAL_CAPITAL,
) -> dict:
    """Run one strategy vs a buy-and-hold benchmark over aligned series."""
    equity = _equity_from_positions(closes, positions, initial)
    bench = _benchmark_equity(benchmark_closes, initial)
    daily = M.daily_returns(equity)
    trades = _round_trip_returns(closes, positions)

    strat_total = M.total_return(equity)
    bench_total = M.total_return(bench)
    metrics = {
        "total_return": round(strat_total, 4),
        "annualized_return": round(M.annualized_return(equity), 4),
        "sharpe": round(M.sharpe_ratio(daily), 3),
        "sortino": round(M.sortino_ratio(daily), 3),
        "max_drawdown": round(M.max_drawdown(equity), 4),
        "win_rate": round(M.win_rate(trades), 4),
        "profit_factor": round(M.profit_factor(trades), 3),
        "avg_trade_return": round(M.average_trade_return(trades), 4),
        "benchmark_total_return": round(bench_total, 4),
        "benchmark_adjusted_return": round(strat_total - bench_total, 4),
        "num_trades": len(trades),
        "final_value": round(equity[-1], 2),
        "benchmark_final_value": round(bench[-1], 2),
    }
    return {
        "metrics": metrics,
        "equity_curve": _downsample(dates, equity, bench),
        "start_date": dates[0],
        "end_date": dates[-1],
    }
