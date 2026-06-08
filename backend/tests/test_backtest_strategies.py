"""Strategy tests — including the no-look-ahead (causality) guarantee."""
from __future__ import annotations

import math

from app.services.backtesting.strategies import STRATEGIES, generate_positions


def _series() -> list[float]:
    # Deterministic wavy uptrend with enough bars for SMA-50.
    return [100 + i * 0.3 + 8 * math.sin(i / 9) for i in range(200)]


def test_positions_are_binary_and_full_length():
    closes = _series()
    for name in STRATEGIES:
        pos = generate_positions(name, closes)
        assert len(pos) == len(closes)
        assert set(pos) <= {0, 1}


def test_buy_and_hold_is_always_long():
    assert generate_positions("buy_and_hold", _series()) == [1] * 200


def test_no_look_ahead_positions_are_causal():
    """A position at bar t must not change when future bars are appended."""
    closes = _series()
    for name in ("sma_crossover", "macd_trend", "rsi_reversion"):
        full = generate_positions(name, closes)
        truncated = generate_positions(name, closes[:120])
        # The first 120 decisions must be identical with or without future data.
        assert truncated == full[:120], name


def test_unknown_strategy_raises():
    import pytest

    with pytest.raises(ValueError):
        generate_positions("nope", _series())
