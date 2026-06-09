"""Execution provider interface and normalized order/fill models.

The portfolio service depends on `ExecutionProvider`, never on a broker SDK.
Two implementations exist: a no-key `SimulatedExecution` (default) and a real
`AlpacaPaperExecution` guarded to the paper endpoint (docs/06-data-sources.md).

**Safety:** there is no live-trading path. The Alpaca provider refuses any base
URL other than the paper host.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol, runtime_checkable

Side = Literal["buy", "sell"]


@dataclass(frozen=True)
class OrderRequest:
    symbol: str
    side: Side
    quantity: float
    asset_type: str = "stock"


@dataclass(frozen=True)
class Fill:
    symbol: str
    side: Side
    quantity: float
    price: float
    order_id: str
    status: str = "filled"


@dataclass(frozen=True)
class BrokerAccount:
    """Normalized brokerage account snapshot."""

    cash: float
    equity: float
    buying_power: float


@dataclass(frozen=True)
class BrokerPosition:
    """Normalized brokerage position (as reported by the broker)."""

    symbol: str
    quantity: float
    avg_cost: float
    current_price: float
    market_value: float
    unrealized_pl: float
    asset_type: str = "stock"  # "stock" | "option"


class ExecutionError(RuntimeError):
    """Raised when an order cannot be placed/filled."""


@runtime_checkable
class ExecutionProvider(Protocol):
    name: str

    def submit_order(self, order: OrderRequest, reference_price: float | None = None) -> Fill:
        """Submit a (paper) market order and return the resulting fill."""
        ...
