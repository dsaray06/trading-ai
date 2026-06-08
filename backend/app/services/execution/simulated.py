"""Simulated (mark-to-model) paper execution.

The default, no-API-key execution provider: fills market orders immediately at
the reference price, or the latest close from the price source. Keeps the whole
accept-recommendation loop demoable without an Alpaca account.
"""
from __future__ import annotations

from uuid import uuid4

from app.core.logging import get_logger
from app.services.data_sources.base import DataSourceError, PriceDataSource
from app.services.execution.base import ExecutionError, Fill, OrderRequest

logger = get_logger(__name__)


class SimulatedExecution:
    name = "simulated"

    def __init__(self, price_source: PriceDataSource) -> None:
        self._price_source = price_source

    def submit_order(self, order: OrderRequest, reference_price: float | None = None) -> Fill:
        price = reference_price if reference_price and reference_price > 0 else None
        if price is None:
            price = self._latest_price(order.symbol)
        fill = Fill(
            symbol=order.symbol,
            side=order.side,
            quantity=order.quantity,
            price=round(price, 4),
            order_id=f"sim-{uuid4()}",
        )
        logger.info("simulated fill: %s %s x%.4f @ %.4f",
                    order.side, order.symbol, order.quantity, price)
        return fill

    def _latest_price(self, symbol: str) -> float:
        try:
            bars = self._price_source.get_daily_bars(symbol, lookback_days=10)
        except DataSourceError as exc:
            raise ExecutionError(f"cannot price {symbol}: {exc}") from exc
        if not bars:
            raise ExecutionError(f"no price available for {symbol}")
        return bars[-1].close
