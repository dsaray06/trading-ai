"""Technical-indicator math — pure, deterministic functions.

These are the numeric heart of the Market Analysis agent and must be reproducible
given identical inputs (docs/03-agents.md, docs/08-coding-standards.md). No I/O,
no randomness, no LLM. Every function takes a sequence of closing prices (oldest
first) and returns plain floats so they unit-test cleanly with fixed fixtures.

Formulas use the conventional definitions:
- SMA: arithmetic mean over the window.
- EMA: exponential moving average, smoothing = 2/(period+1).
- RSI: Wilder's smoothing (alpha = 1/period) over up/down moves, 14-period default.
- MACD: EMA(12) - EMA(26), signal = EMA(9) of the MACD line, hist = MACD - signal.
- Bollinger Bands: SMA(20) +/- num_std * population stdev over the window.
- Volatility: annualized stdev of daily simple returns (252 trading days).
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

TRADING_DAYS = 252


def sma(values: list[float], period: int) -> float:
    """Simple moving average of the last `period` values."""
    if len(values) < period:
        raise ValueError(f"need >= {period} values, got {len(values)}")
    window = values[-period:]
    return sum(window) / period


def ema_series(values: list[float], period: int) -> list[float]:
    """Full EMA series (same length as input). Seeded with the first value."""
    if not values:
        return []
    k = 2.0 / (period + 1)
    out = [values[0]]
    for v in values[1:]:
        out.append(v * k + out[-1] * (1 - k))
    return out


def ema(values: list[float], period: int) -> float:
    """Latest EMA value."""
    if not values:
        raise ValueError("need at least 1 value")
    return ema_series(values, period)[-1]


def rsi(closes: list[float], period: int = 14) -> float:
    """Relative Strength Index using Wilder's smoothing. Returns 0..100.

    Flat series → 50 (neutral). All-up → 100, all-down → 0.
    """
    if len(closes) < period + 1:
        raise ValueError(f"need >= {period + 1} closes, got {len(closes)}")

    gains: list[float] = []
    losses: list[float] = []
    for prev, cur in zip(closes[:-1], closes[1:], strict=False):
        change = cur - prev
        gains.append(max(change, 0.0))
        losses.append(max(-change, 0.0))

    # Wilder's smoothing: seed with the simple average of the first `period`,
    # then smooth the remainder.
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    for g, loss in zip(gains[period:], losses[period:], strict=False):
        avg_gain = (avg_gain * (period - 1) + g) / period
        avg_loss = (avg_loss * (period - 1) + loss) / period

    if avg_loss == 0:
        return 100.0 if avg_gain > 0 else 50.0
    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + rs))


@dataclass(frozen=True)
class Macd:
    macd: float
    signal: float
    histogram: float


def macd(closes: list[float], fast: int = 12, slow: int = 26, signal: int = 9) -> Macd:
    """MACD line, signal line, and histogram."""
    if len(closes) < slow:
        raise ValueError(f"need >= {slow} closes, got {len(closes)}")
    fast_ema = ema_series(closes, fast)
    slow_ema = ema_series(closes, slow)
    macd_line = [f - s for f, s in zip(fast_ema, slow_ema, strict=False)]
    signal_line = ema_series(macd_line, signal)
    return Macd(
        macd=macd_line[-1],
        signal=signal_line[-1],
        histogram=macd_line[-1] - signal_line[-1],
    )


@dataclass(frozen=True)
class Bollinger:
    lower: float
    middle: float
    upper: float
    pct_b: float  # position of last close within the band (0=lower, 1=upper)


def bollinger(closes: list[float], period: int = 20, num_std: float = 2.0) -> Bollinger:
    """Bollinger Bands with population standard deviation over the window."""
    if len(closes) < period:
        raise ValueError(f"need >= {period} closes, got {len(closes)}")
    window = closes[-period:]
    mid = sum(window) / period
    variance = sum((x - mid) ** 2 for x in window) / period
    std = math.sqrt(variance)
    upper = mid + num_std * std
    lower = mid - num_std * std
    width = upper - lower
    pct_b = 0.5 if width == 0 else (closes[-1] - lower) / width
    return Bollinger(lower=lower, middle=mid, upper=upper, pct_b=pct_b)


def daily_returns(closes: list[float]) -> list[float]:
    """Simple daily returns."""
    return [
        (cur - prev) / prev
        for prev, cur in zip(closes[:-1], closes[1:], strict=False)
        if prev != 0
    ]


def annualized_volatility(closes: list[float]) -> float:
    """Annualized volatility as a fraction (e.g. 0.25 = 25%). Population stdev."""
    rets = daily_returns(closes)
    if len(rets) < 2:
        return 0.0
    mean = sum(rets) / len(rets)
    var = sum((r - mean) ** 2 for r in rets) / len(rets)
    return math.sqrt(var) * math.sqrt(TRADING_DAYS)


@dataclass
class IndicatorSet:
    """All computed indicators for one security, ready for scoring and the UI."""

    last_price: float
    sma_20: float
    sma_50: float | None
    ema_12: float
    ema_26: float
    rsi_14: float
    macd: Macd
    bollinger: Bollinger
    annualized_volatility: float
    extras: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "last_price": round(self.last_price, 4),
            "sma_20": round(self.sma_20, 4),
            "sma_50": round(self.sma_50, 4) if self.sma_50 is not None else None,
            "ema_12": round(self.ema_12, 4),
            "ema_26": round(self.ema_26, 4),
            "rsi_14": round(self.rsi_14, 2),
            "macd": {
                "macd": round(self.macd.macd, 4),
                "signal": round(self.macd.signal, 4),
                "histogram": round(self.macd.histogram, 4),
            },
            "bollinger": {
                "lower": round(self.bollinger.lower, 4),
                "middle": round(self.bollinger.middle, 4),
                "upper": round(self.bollinger.upper, 4),
                "pct_b": round(self.bollinger.pct_b, 4),
            },
            "annualized_volatility": round(self.annualized_volatility, 4),
            **self.extras,
        }


def compute_indicators(closes: list[float]) -> IndicatorSet:
    """Compute the full indicator set from a close-price series (oldest first).

    Requires at least 26 closes (for MACD slow EMA). SMA-50 is included only when
    enough history is present.
    """
    if len(closes) < 26:
        raise ValueError(f"need >= 26 closes for a full indicator set, got {len(closes)}")
    return IndicatorSet(
        last_price=closes[-1],
        sma_20=sma(closes, 20),
        sma_50=sma(closes, 50) if len(closes) >= 50 else None,
        ema_12=ema(closes, 12),
        ema_26=ema(closes, 26),
        rsi_14=rsi(closes, 14),
        macd=macd(closes),
        bollinger=bollinger(closes),
        annualized_volatility=annualized_volatility(closes),
    )
