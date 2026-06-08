"""Unit tests for indicator math against fixed, hand-verifiable inputs."""
from __future__ import annotations

import math

import pytest

from app.services import indicators as ind


def test_sma_known_value():
    assert ind.sma(list(range(1, 21)), 20) == pytest.approx(10.5)


def test_ema_constant_series_equals_constant():
    assert ind.ema([5.0] * 30, 12) == pytest.approx(5.0)


def test_rsi_all_gains_is_100():
    closes = [100 + i for i in range(20)]
    assert ind.rsi(closes, 14) == pytest.approx(100.0)


def test_rsi_all_losses_is_0():
    closes = [200 - i for i in range(20)]
    assert ind.rsi(closes, 14) == pytest.approx(0.0)


def test_rsi_flat_series_is_50():
    assert ind.rsi([50.0] * 20, 14) == pytest.approx(50.0)


def test_rsi_known_mixed_value():
    # 14 changes: thirteen +1 then one -1 → avg_gain=13/14, avg_loss=1/14, RS=13.
    # RSI = 100 - 100/(1+13) = 92.857142...
    closes = [100, 101, 102, 103, 104, 105, 106, 107, 108, 109, 110, 111, 112, 113, 112]
    assert ind.rsi(closes, 14) == pytest.approx(92.857142, abs=1e-4)


def test_macd_constant_series_is_zero():
    m = ind.macd([10.0] * 40)
    assert m.macd == pytest.approx(0.0)
    assert m.signal == pytest.approx(0.0)
    assert m.histogram == pytest.approx(0.0)


def test_bollinger_constant_series_collapses():
    b = ind.bollinger([7.0] * 25, period=20)
    assert b.lower == pytest.approx(7.0)
    assert b.middle == pytest.approx(7.0)
    assert b.upper == pytest.approx(7.0)
    assert b.pct_b == pytest.approx(0.5)


def test_bollinger_width_matches_two_std():
    closes = [float(x) for x in range(1, 21)]  # 1..20
    b = ind.bollinger(closes, period=20, num_std=2.0)
    mean = sum(closes) / 20
    std = math.sqrt(sum((x - mean) ** 2 for x in closes) / 20)
    assert b.upper == pytest.approx(mean + 2 * std)
    assert b.lower == pytest.approx(mean - 2 * std)


def test_annualized_volatility_constant_is_zero():
    assert ind.annualized_volatility([100.0] * 30) == pytest.approx(0.0)


def test_compute_indicators_requires_min_history():
    with pytest.raises(ValueError):
        ind.compute_indicators([1.0] * 20)


def test_compute_indicators_full_set():
    closes = [100 + math.sin(i / 5) * 3 + i * 0.1 for i in range(120)]
    s = ind.compute_indicators(closes)
    assert s.last_price == pytest.approx(closes[-1])
    assert s.sma_50 is not None
    d = s.to_dict()
    assert 0 <= d["rsi_14"] <= 100
    assert "macd" in d and "bollinger" in d
