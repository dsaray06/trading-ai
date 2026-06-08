"""Unit tests for the deterministic Market-agent scoring."""
from __future__ import annotations

import pytest

from app.agents import scoring
from app.services.indicators import Bollinger, IndicatorSet, Macd


def _make(
    *,
    last_price: float,
    sma_20: float,
    sma_50: float | None,
    ema_12: float,
    ema_26: float,
    rsi: float,
    hist: float,
    vol: float,
) -> IndicatorSet:
    return IndicatorSet(
        last_price=last_price,
        sma_20=sma_20,
        sma_50=sma_50,
        ema_12=ema_12,
        ema_26=ema_26,
        rsi_14=rsi,
        macd=Macd(macd=ema_12 - ema_26, signal=0.0, histogram=hist),
        bollinger=Bollinger(lower=last_price - 1, middle=last_price, upper=last_price + 1,
                            pct_b=0.5),
        annualized_volatility=vol,
    )


def test_strong_uptrend_scores_bullish_and_votes_buy():
    s = _make(last_price=120, sma_20=110, sma_50=100, ema_12=118, ema_26=112,
              rsi=62, hist=1.5, vol=0.2)
    assert scoring.trend_subscore(s) == pytest.approx(93.0)
    assert scoring.classify_trend(s) == "strong_up"
    assert scoring.action_for_score(scoring.technical_score(s)) == "Buy"


def test_strong_downtrend_votes_sell():
    s = _make(last_price=80, sma_20=90, sma_50=100, ema_12=82, ema_26=88,
              rsi=35, hist=-1.5, vol=0.3)
    assert scoring.classify_trend(s) == "strong_down"
    assert scoring.action_for_score(scoring.technical_score(s)) == "Sell"


def test_volatility_subscore_scales_and_clamps():
    s_low = _make(last_price=100, sma_20=100, sma_50=100, ema_12=100, ema_26=100,
                  rsi=50, hist=0.0, vol=0.30)
    assert scoring.volatility_subscore(s_low) == pytest.approx(50.0)
    s_high = _make(last_price=100, sma_20=100, sma_50=100, ema_12=100, ema_26=100,
                   rsi=50, hist=0.0, vol=1.5)
    assert scoring.volatility_subscore(s_high) == pytest.approx(100.0)


def test_scores_are_bounded():
    s = _make(last_price=120, sma_20=110, sma_50=100, ema_12=118, ema_26=112,
              rsi=99, hist=5.0, vol=2.0)
    assert 0 <= scoring.technical_score(s) <= 100
    assert 0 <= scoring.momentum_subscore(s) <= 100
