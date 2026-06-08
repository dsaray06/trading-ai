"""Backtest runner: fetch + align prices, replay a strategy, persist the result.

Thin orchestration around the pure engine. Fetches the symbol and benchmark,
aligns them on common trading days, slices to the requested horizon, runs the
strategy, and stores a `Backtest` row. Price source is injected for testing.
"""
from __future__ import annotations

from datetime import timedelta

from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.models.backtest import Backtest
from app.models.user import User
from app.schemas.backtest import BacktestRequest
from app.services.backtesting.engine import run_backtest
from app.services.backtesting.strategies import STRATEGIES, generate_positions
from app.services.data_sources.base import DataSourceError, PriceDataSource
from app.services.data_sources.yfinance_source import YFinancePriceSource

logger = get_logger(__name__)

_HORIZON_YEARS = {"1Y": 1, "3Y": 3, "5Y": 5, "10Y": 10}
_MIN_BARS = 60


class BacktestError(RuntimeError):
    """Raised when a backtest can't be run (bad strategy, no data, etc.)."""


def run_and_store(
    db: Session,
    user: User,
    req: BacktestRequest,
    price_source: PriceDataSource | None = None,
) -> Backtest:
    if req.strategy not in STRATEGIES:
        raise BacktestError(f"Unknown strategy '{req.strategy}'")
    source = price_source or YFinancePriceSource()

    symbol = req.symbol.upper().strip()
    bench_symbol = (req.benchmark_symbol or "SPY").upper().strip() \
        if req.benchmark == "custom" else req.benchmark
    years = _HORIZON_YEARS[req.horizon]
    lookback = years * 365 + 20

    try:
        sym_bars = source.get_daily_bars(symbol, lookback)
        bm_bars = source.get_daily_bars(bench_symbol, lookback)
    except DataSourceError as exc:
        raise BacktestError(str(exc)) from exc

    bm_map = {b.day: b.close for b in bm_bars}
    common = sorted(b.day for b in sym_bars if b.day in bm_map)
    if common:
        cutoff = common[-1] - timedelta(days=years * 365)
        common = [d for d in common if d >= cutoff]
    if len(common) < _MIN_BARS:
        raise BacktestError(
            f"Not enough overlapping history for {symbol}/{bench_symbol} "
            f"({len(common)} bars)."
        )

    sym_map = {b.day: b.close for b in sym_bars}
    dates = [d.isoformat() for d in common]
    closes = [sym_map[d] for d in common]
    bm_closes = [bm_map[d] for d in common]

    positions = generate_positions(req.strategy, closes)
    result = run_backtest(dates, closes, positions, bm_closes)

    bt = Backtest(
        user_id=user.id,
        strategy=req.strategy,
        symbol=symbol,
        benchmark=bench_symbol,
        horizon=req.horizon,
        start_date=common[0],
        end_date=common[-1],
        params=req.params,
        metrics=result["metrics"],
        equity_curve=result["equity_curve"],
    )
    db.add(bt)
    db.commit()
    db.refresh(bt)
    logger.info(
        "backtest %s on %s vs %s (%s): total %.1f%% vs bench %.1f%%, %d trades",
        req.strategy, symbol, bench_symbol, req.horizon,
        result["metrics"]["total_return"] * 100,
        result["metrics"]["benchmark_total_return"] * 100,
        result["metrics"]["num_trades"],
    )
    return bt
