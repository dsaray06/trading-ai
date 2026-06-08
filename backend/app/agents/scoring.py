"""Deterministic technical scoring for the Market Analysis agent.

Pure functions over an `IndicatorSet`. No I/O, no LLM, no randomness — given the
same indicators they always return the same scores, so they unit-test against
fixed fixtures (docs/03-agents.md, docs/08-coding-standards.md). The LLM only
writes the prose explanation; these numbers are the reproducible core.

Scores are 0-100, higher = more bullish (except `volatility_score`, where higher
= more volatile).
"""
from __future__ import annotations

from app.schemas.agents import Trend
from app.services.indicators import IndicatorSet

# Annualized volatility (as a fraction) that maps to a volatility_score of 100.
_VOL_FULL_SCALE = 0.60


def _clamp(x: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, x))


def trend_subscore(ind: IndicatorSet) -> float:
    """Trend-following score from price/MA structure, EMA cross, and MACD sign."""
    score = 50.0
    score += 10 if ind.last_price > ind.sma_20 else -10
    if ind.sma_50 is not None:
        score += 8 if ind.last_price > ind.sma_50 else -8
        score += 7 if ind.sma_20 > ind.sma_50 else -7  # golden/death alignment
    score += 10 if ind.ema_12 > ind.ema_26 else -10
    score += 8 if ind.macd.histogram > 0 else -8
    return _clamp(score)


def momentum_subscore(ind: IndicatorSet) -> float:
    """Momentum from RSI (already directional 0-100) plus MACD-histogram sign."""
    rsi_component = ind.rsi_14
    macd_component = 60.0 if ind.macd.histogram > 0 else 40.0
    return _clamp(0.6 * rsi_component + 0.4 * macd_component)


def volatility_subscore(ind: IndicatorSet) -> float:
    """Higher = more volatile. Linear in annualized volatility, clamped to 0-100."""
    return _clamp(ind.annualized_volatility / _VOL_FULL_SCALE * 100.0)


def technical_score(ind: IndicatorSet) -> float:
    """Overall bullishness: trend + momentum, penalized for overbought/extreme vol."""
    base = 0.6 * trend_subscore(ind) + 0.4 * momentum_subscore(ind)
    if ind.rsi_14 > 75:
        base -= 8  # overbought — stretched
    if ind.rsi_14 < 25:
        base -= 4  # oversold — possible reversal but uncertain
    if ind.annualized_volatility > _VOL_FULL_SCALE:
        base -= 5  # high vol lowers conviction
    return _clamp(base)


def classify_trend(ind: IndicatorSet) -> Trend:
    t = trend_subscore(ind)
    if t >= 75:
        return "strong_up"
    if t >= 58:
        return "up"
    if t > 42:
        return "sideways"
    if t > 25:
        return "down"
    return "strong_down"


def action_for_score(score: float) -> str:
    """Map an overall bullishness score to a discrete action."""
    if score >= 66:
        return "Buy"
    if score >= 45:
        return "Hold"
    return "Sell"
