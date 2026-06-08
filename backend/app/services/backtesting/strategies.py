"""Backtest strategies: causal long/flat signal generators.

Each strategy maps a close-price series to a position series (1 = long, 0 = flat)
where position[t] depends only on prices up to and including bar t — never the
future. Indicators are computed with pandas (rolling / ewm are causal). These are
deterministic technical rules, not the LLM agents: backtests must be reproducible
and must not let a strategy peek ahead (docs/06, docs/07 Phase 5).
"""
from __future__ import annotations

import math
from collections.abc import Callable

import pandas as pd


def _rsi(s: pd.Series, n: int = 14) -> pd.Series:
    delta = s.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / n, adjust=False, min_periods=n).mean()
    avg_loss = loss.ewm(alpha=1 / n, adjust=False, min_periods=n).mean()
    rs = avg_gain / avg_loss
    return 100 - 100 / (1 + rs)


def _macd_hist(s: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.Series:
    macd = s.ewm(span=fast, adjust=False).mean() - s.ewm(span=slow, adjust=False).mean()
    return macd - macd.ewm(span=signal, adjust=False).mean()


def buy_and_hold(closes: list[float]) -> list[int]:
    return [1] * len(closes)


def sma_crossover(closes: list[float], short: int = 20, long: int = 50) -> list[int]:
    s = pd.Series(closes, dtype="float64")
    signal = s.rolling(short).mean() > s.rolling(long).mean()
    return signal.fillna(False).astype(int).tolist()


def macd_trend(closes: list[float]) -> list[int]:
    s = pd.Series(closes, dtype="float64")
    return (_macd_hist(s) > 0).fillna(False).astype(int).tolist()


def rsi_reversion(closes: list[float], low: float = 30, high: float = 55) -> list[int]:
    """Enter long when oversold (RSI<low), exit when RSI>high; hold in between."""
    rsi = _rsi(pd.Series(closes, dtype="float64"))
    positions: list[int] = []
    holding = False
    for r in rsi:
        if not math.isnan(r):
            if not holding and r < low:
                holding = True
            elif holding and r > high:
                holding = False
        positions.append(1 if holding else 0)
    return positions


STRATEGIES: dict[str, Callable[[list[float]], list[int]]] = {
    "buy_and_hold": buy_and_hold,
    "sma_crossover": sma_crossover,
    "macd_trend": macd_trend,
    "rsi_reversion": rsi_reversion,
}

STRATEGY_LABELS = {
    "buy_and_hold": "Buy & Hold",
    "sma_crossover": "SMA 20/50 Crossover",
    "macd_trend": "MACD Trend",
    "rsi_reversion": "RSI Mean Reversion",
}


def generate_positions(strategy: str, closes: list[float]) -> list[int]:
    if strategy not in STRATEGIES:
        raise ValueError(f"unknown strategy '{strategy}'")
    return STRATEGIES[strategy](closes)
