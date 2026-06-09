"""Deterministic fake data sources for offline tests (no network, no LLM key)."""
from __future__ import annotations

import math
from datetime import date, timedelta

from app.services.data_sources.base import (
    AnalystRecommendations,
    DataSourceError,
    Fundamentals,
    NewsItem,
    OptionChain,
    OptionContract,
    PriceBar,
    SentimentData,
)


class FakeUptrendSource:
    """Deterministic gently-rising price series."""

    def get_daily_bars(self, symbol: str, lookback_days: int = 365) -> list[PriceBar]:
        start = date(2025, 1, 1)
        bars: list[PriceBar] = []
        for i in range(150):
            close = 100 + i * 0.5 + math.sin(i / 6) * 1.5
            bars.append(
                PriceBar(
                    day=start + timedelta(days=i),
                    open=close - 0.2,
                    high=close + 0.5,
                    low=close - 0.5,
                    close=close,
                    volume=1_000_000,
                )
            )
        return bars


class FakeFundamentalsSource:
    """Solid, undervalued-ish company."""

    def get_fundamentals(self, symbol: str) -> Fundamentals:
        return Fundamentals(
            symbol=symbol.upper(),
            name="Fake Co",
            sector="Technology",
            market_cap=5e11,
            pe=18.0,
            forward_pe=16.0,
            pb=3.0,
            profit_margin=0.22,
            revenue_growth=0.15,
            earnings_growth=0.18,
            debt_to_equity=80.0,
            roe=0.20,
            free_cash_flow=2e10,
        )


class FakeNewsSource:
    """Positive headlines + bullish analyst skew."""

    def get_sentiment_data(self, symbol: str, limit: int = 20) -> SentimentData:
        return SentimentData(
            news=[
                NewsItem(title="Company beats earnings and raises guidance"),
                NewsItem(title="Analysts upgrade on strong revenue growth"),
                NewsItem(title="New product launch boosts outlook"),
            ],
            analysts=AnalystRecommendations(
                strong_buy=5, buy=10, hold=3, sell=1, strong_sell=0
            ),
        )


class FakeOptionsSource:
    """Deterministic option chain around a $175 spot."""

    def get_option_chain(self, symbol: str, target_dte: int = 30) -> OptionChain:
        expiry = date(2025, 2, 15)
        dte = 32
        spot = 175.0

        def mk(opt_type: str, strike: float) -> OptionContract:
            return OptionContract(
                contract_symbol=f"{symbol}250215{opt_type[0].upper()}{int(strike * 1000):08d}",
                underlying=symbol, opt_type=opt_type, strike=strike, expiry=expiry,
                dte=dte, premium=5.0, bid=4.9, ask=5.1, implied_volatility=0.40,
                volume=1000, open_interest=2000,
            )

        return OptionChain(
            underlying=symbol, spot=spot, expiry=expiry, dte=dte,
            calls=[mk("call", s) for s in (170, 175, 180, 185, 190)],
            puts=[mk("put", s) for s in (160, 165, 170, 175, 180)],
        )


class FakeAlpacaBroker:
    """In-memory stand-in for the Alpaca paper broker (no SDK, no network)."""

    name = "alpaca-paper"

    def __init__(self, cash: float = 100_000.0) -> None:
        from app.services.execution.base import BrokerPosition

        self._cash = cash
        self._positions: list[BrokerPosition] = []
        self.orders: list = []

    def get_account(self):
        from app.services.execution.base import BrokerAccount

        equity = self._cash + sum(p.market_value for p in self._positions)
        return BrokerAccount(cash=self._cash, equity=equity, buying_power=self._cash * 2)

    def get_positions(self):
        return list(self._positions)

    def submit_order(self, order, reference_price=None):
        from app.services.execution.base import BrokerPosition, Fill

        price = reference_price or 100.0
        self.orders.append(order)
        mult = 100 if order.asset_type == "option" else 1
        if order.side == "buy":
            self._cash -= order.quantity * price * mult
            self._positions.append(BrokerPosition(
                symbol=order.symbol, quantity=order.quantity, avg_cost=price,
                current_price=price, market_value=order.quantity * price * mult,
                unrealized_pl=0.0, asset_type=order.asset_type,
            ))
        else:
            self._cash += order.quantity * price
            self._positions = [p for p in self._positions if p.symbol != order.symbol]
        return Fill(symbol=order.symbol, side=order.side, quantity=order.quantity,
                    price=price, order_id="alp-test-1", status="filled")


class FailingSource:
    """Any fetch raises — used to exercise the abstain path."""

    def get_daily_bars(self, symbol: str, lookback_days: int = 365):
        raise DataSourceError("boom")

    def get_fundamentals(self, symbol: str):
        raise DataSourceError("boom")

    def get_sentiment_data(self, symbol: str, limit: int = 20):
        raise DataSourceError("boom")

    def get_option_chain(self, symbol: str, target_dte: int = 30):
        raise DataSourceError("boom")
