"""Unit tests for Black-Scholes math and the Options Analysis agent."""
from __future__ import annotations

import pytest

from app.agents.options import run_options_agent
from app.services.options_math import black_scholes_price, option_metrics
from tests.fakes import FakeOptionsSource


def test_bs_call_known_value():
    # S=100,K=100,T=1,r=0.05,sigma=0.2 -> textbook call 10.4506, put 5.5735.
    call = black_scholes_price(100, 100, 1, 0.05, 0.2, "call")
    put = black_scholes_price(100, 100, 1, 0.05, 0.2, "put")
    assert call == pytest.approx(10.4506, abs=1e-3)
    assert put == pytest.approx(5.5735, abs=1e-3)


def test_put_call_parity():
    import math
    s, k, t, r, sig = 100, 95, 0.5, 0.03, 0.25
    call = black_scholes_price(s, k, t, r, sig, "call")
    put = black_scholes_price(s, k, t, r, sig, "put")
    assert call - put == pytest.approx(s - k * math.exp(-r * t), abs=1e-6)


def test_call_delta_and_greeks_signs():
    m = option_metrics(100, 100, 1, 0.05, 0.2, "call")
    assert m.delta == pytest.approx(0.6368, abs=1e-3)
    assert m.gamma > 0
    assert m.vega > 0
    assert m.theta < 0  # long option decays


def test_expired_option_is_intrinsic():
    m = option_metrics(120, 100, 0.0, 0.05, 0.2, "call")
    assert m.price == pytest.approx(20.0)
    assert m.intrinsic == pytest.approx(20.0)


def test_options_agent_bullish_buys_call():
    chain = FakeOptionsSource().get_option_chain("NVDA")
    out = run_options_agent("NVDA", chain, bullish=True, strength=80)
    assert out.vote.action == "Buy Call"
    assert out.vote.abstain is False
    assert out.premium > 0
    assert out.contract_symbol
    assert set(out.greeks) >= {"delta", "gamma", "theta", "vega"}
    assert {"max_gain", "max_loss", "breakeven", "ratio"} <= set(out.risk_reward)
    # ~5% OTM call selected around a $175 spot.
    assert out.strike_recommendation == 185


def test_options_agent_bearish_buys_put():
    chain = FakeOptionsSource().get_option_chain("NVDA")
    out = run_options_agent("NVDA", chain, bullish=False, strength=30)
    assert out.vote.action == "Buy Put"
    assert out.strike_recommendation == 165  # ~5% OTM put
