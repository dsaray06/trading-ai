"""Tests for execution providers (simulated fills + Alpaca paper guard)."""
from __future__ import annotations

import pytest

from app.services.execution.alpaca import AlpacaPaperExecution
from app.services.execution.base import ExecutionError, OrderRequest
from app.services.execution.simulated import SimulatedExecution
from tests.fakes import FakeUptrendSource


def test_simulated_fills_at_reference_price():
    ex = SimulatedExecution(FakeUptrendSource())
    fill = ex.submit_order(OrderRequest("TEST", "buy", 5), reference_price=123.45)
    assert fill.price == 123.45
    assert fill.quantity == 5
    assert fill.side == "buy"
    assert fill.status == "filled"
    assert fill.order_id.startswith("sim-")


def test_simulated_falls_back_to_latest_close():
    ex = SimulatedExecution(FakeUptrendSource())
    fill = ex.submit_order(OrderRequest("TEST", "buy", 1))  # no reference price
    # FakeUptrendSource last close is the 150th bar.
    assert fill.price > 100


def test_alpaca_guard_refuses_non_paper_url(monkeypatch):
    from app.core import config

    settings = config.get_settings()
    monkeypatch.setattr(settings, "alpaca_base_url", "https://api.alpaca.markets")
    monkeypatch.setattr(settings, "alpaca_api_key", "k")
    monkeypatch.setattr(settings, "alpaca_api_secret", "s")
    with pytest.raises(ExecutionError, match="paper host"):
        AlpacaPaperExecution()


def test_alpaca_not_configured_by_default():
    # No keys in the test environment -> provider reports unconfigured.
    assert AlpacaPaperExecution.is_configured() is False
