"""Alpaca paper-trading broker.

Used when Alpaca API keys are configured. Submits paper orders AND reads the
account/positions so an Alpaca-linked portfolio can mirror the real paper account
(docs/06-data-sources.md). **Hard safety guard:** construction fails unless the
base URL is the Alpaca *paper* host — there is no live-trading path
(docs/08-coding-standards.md §Security).

The trading client is built lazily via `_make_trading_client` (and is injectable)
so the SDK import only happens when actually talking to Alpaca.
"""
from __future__ import annotations

from app.core.config import get_settings
from app.core.logging import get_logger
from app.services.execution.base import (
    BrokerAccount,
    BrokerPosition,
    ExecutionError,
    Fill,
    OrderRequest,
)

logger = get_logger(__name__)

_PAPER_HOST = "paper-api.alpaca.markets"


def _make_trading_client(api_key: str, api_secret: str):
    """Build a real alpaca-py paper TradingClient (lazy import)."""
    from alpaca.trading.client import TradingClient

    return TradingClient(api_key, api_secret, paper=True)


def _f(value, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


class AlpacaPaperExecution:
    name = "alpaca-paper"

    def __init__(self, client=None, api_key: str | None = None,
                 api_secret: str | None = None) -> None:
        settings = get_settings()
        if _PAPER_HOST not in settings.alpaca_base_url:
            raise ExecutionError(
                f"Refusing to start: ALPACA_BASE_URL must be the paper host "
                f"({_PAPER_HOST}); got {settings.alpaca_base_url!r}."
            )
        # Per-user keys take precedence over any server-global keys.
        self._key = api_key or settings.alpaca_api_key
        self._secret = api_secret or settings.alpaca_api_secret
        if not self._key or not self._secret:
            raise ExecutionError("Alpaca API key/secret not configured.")
        self._client = client  # injectable for tests

    @staticmethod
    def is_configured() -> bool:
        settings = get_settings()
        return bool(
            settings.alpaca_api_key
            and settings.alpaca_api_secret
            and _PAPER_HOST in settings.alpaca_base_url
        )

    def _trading(self):
        if self._client is None:
            self._client = _make_trading_client(self._key, self._secret)
        return self._client

    # ---- account / positions (mirror) ------------------------------------

    def get_account(self) -> BrokerAccount:
        try:
            acct = self._trading().get_account()
            return BrokerAccount(
                cash=_f(acct.cash),
                equity=_f(acct.equity),
                buying_power=_f(acct.buying_power),
            )
        except ExecutionError:
            raise
        except Exception as exc:  # noqa: BLE001 - translate broker SDK errors
            raise ExecutionError(f"alpaca get_account failed: {exc}") from exc

    def get_positions(self) -> list[BrokerPosition]:
        try:
            raw = self._trading().get_all_positions()
        except Exception as exc:  # noqa: BLE001 - translate broker SDK errors
            raise ExecutionError(f"alpaca get_positions failed: {exc}") from exc
        out: list[BrokerPosition] = []
        for p in raw:
            # asset_class is an AssetClass enum ("us_equity" | "us_option").
            asset_class = getattr(getattr(p, "asset_class", None), "value", None) or str(
                getattr(p, "asset_class", "")
            )
            out.append(BrokerPosition(
                symbol=str(p.symbol),
                quantity=_f(p.qty),
                avg_cost=_f(getattr(p, "avg_entry_price", None)),
                current_price=_f(getattr(p, "current_price", None)),
                market_value=_f(getattr(p, "market_value", None)),
                unrealized_pl=_f(getattr(p, "unrealized_pl", None)),
                asset_type="option" if "option" in asset_class else "stock",
            ))
        return out

    # ---- order submission -------------------------------------------------

    def submit_order(self, order: OrderRequest, reference_price: float | None = None) -> Fill:
        try:
            from alpaca.trading.enums import OrderSide, TimeInForce
            from alpaca.trading.requests import MarketOrderRequest

            # Options use the same market-order path: the symbol is the OCC contract
            # symbol and qty is the number of contracts (Alpaca applies the 100x
            # multiplier to buying power). Requires options trading enabled on the
            # account (see the error hint below if it isn't).
            req = MarketOrderRequest(
                symbol=order.symbol,
                qty=order.quantity,
                side=OrderSide.BUY if order.side == "buy" else OrderSide.SELL,
                time_in_force=TimeInForce.DAY,
            )
            submitted = self._trading().submit_order(req)
            filled_price = _f(getattr(submitted, "filled_avg_price", None),
                              reference_price or 0.0)
            # status is an OrderStatus enum; use its .value ("pending_new", "filled", ...)
            status_obj = getattr(submitted, "status", None)
            status = getattr(status_obj, "value", None) or (
                str(status_obj) if status_obj else "accepted"
            )
            return Fill(
                symbol=order.symbol,
                side=order.side,
                quantity=order.quantity,
                price=round(filled_price, 4),
                order_id=str(submitted.id),
                status=status,
            )
        except ExecutionError:
            raise
        except Exception as exc:  # noqa: BLE001 - translate broker SDK errors
            logger.warning("alpaca order failed for %s: %s", order.symbol, exc)
            hint = ""
            if order.asset_type == "option" and "option" in str(exc).lower():
                hint = (
                    " — enable options trading on your Alpaca paper account "
                    "(Account → Configure → Options) and try again"
                )
            raise ExecutionError(
                f"alpaca order failed for {order.symbol}: {exc}{hint}"
            ) from exc
