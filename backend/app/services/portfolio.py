"""Portfolio service: creation, paper-execution accounting, and reviews.

Holds the money/position logic for accepting a recommendation into a simulated
portfolio. Money and quantities use `Decimal`. Execution goes through the
`ExecutionProvider` interface (simulated by default; Alpaca paper if configured).
"""
from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from sqlalchemy.orm import Session

from app.agents.holdings_review import PositionView, run_holdings_review
from app.agents.portfolio_risk import HoldingExposure, portfolio_risk_metrics, position_size
from app.core.logging import get_logger
from app.models.portfolio import Portfolio, Position, Trade
from app.models.recommendation import Recommendation
from app.models.user import User
from app.schemas.portfolio import (
    AllocationOut,
    AllocationSlice,
    HoldingReviewItem,
    PortfolioSummary,
    PositionOut,
    ReviewResponse,
    TradeOut,
)
from app.services.data_sources.base import DataSourceError, PriceDataSource
from app.services.execution.alpaca import AlpacaPaperExecution
from app.services.execution.base import ExecutionError, ExecutionProvider, OrderRequest
from app.services.execution.simulated import SimulatedExecution

logger = get_logger(__name__)

_BUY_ACTIONS = {"Buy", "Add", "Buy ETF"}
_SELL_ACTIONS = {"Sell", "Trim"}
_OPTION_BUY = {"Buy Call", "Buy Put"}  # long options open via a buy
_OPTION_MULTIPLIER = 100  # one contract controls 100 shares


class PortfolioError(RuntimeError):
    """Base for portfolio service errors."""


class NotFound(PortfolioError):
    pass


class Forbidden(PortfolioError):
    pass


class TradeRejected(PortfolioError):
    pass


def _dec(x: float | Decimal) -> Decimal:
    return Decimal(str(round(float(x), 4)))


def build_execution(price_source: PriceDataSource) -> ExecutionProvider:
    """Use Alpaca paper if fully configured, else the simulated provider."""
    if AlpacaPaperExecution.is_configured():
        try:
            return AlpacaPaperExecution()
        except ExecutionError as exc:
            logger.warning("Alpaca unavailable (%s); falling back to simulated", exc)
    return SimulatedExecution(price_source)


def _latest_price(price_source: PriceDataSource, symbol: str) -> float:
    try:
        bars = price_source.get_daily_bars(symbol, lookback_days=10)
    except DataSourceError as exc:
        raise TradeRejected(f"cannot price {symbol}: {exc}") from exc
    if not bars:
        raise TradeRejected(f"no price available for {symbol}")
    return bars[-1].close


def _market_value(p: Position) -> float:
    mult = _OPTION_MULTIPLIER if p.asset_type == "option" else 1
    return float(p.quantity) * float(p.current_price) * mult


def _positions_value(pf: Portfolio) -> float:
    return sum(_market_value(p) for p in pf.positions)


# ---- portfolio CRUD -------------------------------------------------------

def create_portfolio(
    db: Session, user: User, name: str, starting_cash: float,
    broker: str = "simulated", alpaca_broker=None,
) -> Portfolio:
    if broker == "alpaca":
        if alpaca_broker is None:
            raise PortfolioError("Alpaca is not configured on this server")
        try:
            account = alpaca_broker.get_account()
        except ExecutionError as exc:
            raise PortfolioError(f"Could not reach Alpaca: {exc}") from exc
        pf = Portfolio(
            user_id=user.id, name=name, broker="alpaca",
            starting_cash=_dec(account.equity), cash_balance=_dec(account.cash),
        )
        db.add(pf)
        db.commit()
        db.refresh(pf)
        _sync_from_alpaca(db, pf, alpaca_broker)
        return pf

    pf = Portfolio(
        user_id=user.id, name=name, broker="simulated",
        starting_cash=_dec(starting_cash), cash_balance=_dec(starting_cash),
    )
    db.add(pf)
    db.commit()
    db.refresh(pf)
    return pf


def list_portfolios(db: Session, user: User) -> list[Portfolio]:
    return db.query(Portfolio).filter(Portfolio.user_id == user.id).all()


def get_owned_portfolio(db: Session, user: User, portfolio_id: UUID) -> Portfolio:
    pf = db.get(Portfolio, portfolio_id)
    if pf is None:
        raise NotFound("Portfolio not found")
    if pf.user_id != user.id:
        raise Forbidden("Not your portfolio")
    return pf


# ---- pricing / valuation --------------------------------------------------

def sync_prices(db: Session, pf: Portfolio, price_source: PriceDataSource) -> None:
    """Refresh each position's current price + unrealized P/L from the price source."""
    changed = False
    for pos in pf.positions:
        if pos.asset_type == "option":
            continue  # mark-to-model option positions hold their entry mark
        try:
            price = _latest_price(price_source, pos.symbol)
        except TradeRejected:
            continue  # keep last known mark if pricing is briefly unavailable
        pos.current_price = _dec(price)
        pos.unrealized_pl = _dec((price - float(pos.avg_cost)) * float(pos.quantity))
        changed = True
    if changed:
        db.commit()


def _sync_from_alpaca(db: Session, pf: Portfolio, broker) -> None:
    """Mirror the Alpaca paper account (cash + positions) into the portfolio."""
    try:
        account = broker.get_account()
        positions = broker.get_positions()
    except ExecutionError as exc:
        raise PortfolioError(f"Alpaca sync failed: {exc}") from exc
    pf.cash_balance = _dec(account.cash)
    pf.positions = [
        Position(
            symbol=p.symbol, asset_type="stock", quantity=_dec(p.quantity),
            avg_cost=_dec(p.avg_cost), current_price=_dec(p.current_price),
            unrealized_pl=_dec(p.unrealized_pl),
        )
        for p in positions
    ]
    db.commit()


def sync_portfolio_state(
    db: Session, pf: Portfolio, price_source: PriceDataSource, broker=None
) -> None:
    """Refresh portfolio marks: from Alpaca for linked portfolios, else price source."""
    if pf.broker == "alpaca":
        if broker is None:
            raise PortfolioError("Alpaca is not configured to sync this portfolio")
        _sync_from_alpaca(db, pf, broker)
    else:
        sync_prices(db, pf, price_source)


# ---- accept a recommendation (paper trade) --------------------------------

def accept_recommendation(
    db: Session,
    pf: Portfolio,
    recommendation_id: UUID,
    quantity: float | None,
    override_price: float | None,
    price_source: PriceDataSource,
    execution: ExecutionProvider,
) -> Trade:
    """Turn a recommendation into a paper trade. Idempotent per recommendation."""
    existing = (
        db.query(Trade)
        .filter(Trade.portfolio_id == pf.id, Trade.recommendation_id == recommendation_id)
        .first()
    )
    if existing is not None:
        logger.info("idempotent: recommendation %s already traded in portfolio %s",
                    recommendation_id, pf.id)
        return existing

    rec = db.get(Recommendation, recommendation_id)
    if rec is None:
        raise NotFound("Recommendation not found")

    symbol = rec.symbol
    action = rec.action
    is_option = rec.asset_type == "option"
    if action in _BUY_ACTIONS or action in _OPTION_BUY:
        side = "buy"
    elif action in _SELL_ACTIONS:
        side = "sell"
    else:
        raise TradeRejected(f"'{action}' is not an executable trade")

    if pf.broker == "alpaca":
        return _accept_via_alpaca(
            db, pf, rec, recommendation_id, symbol, side, is_option,
            quantity, override_price, price_source, execution,
        )

    price = override_price or (float(rec.entry_target) if rec.entry_target else None)
    if not price or price <= 0:
        if is_option:
            raise TradeRejected(f"No premium available for option {symbol}")
        price = _latest_price(price_source, symbol)
    multiplier = _OPTION_MULTIPLIER if is_option else 1

    pos = next((p for p in pf.positions if p.symbol == symbol), None)
    qty = _resolve_quantity(quantity, rec, side, price, pf, pos, multiplier, is_option)

    fill = execution.submit_order(
        OrderRequest(symbol=symbol, side=side, quantity=qty, asset_type=rec.asset_type),
        reference_price=price,
    )

    _apply_fill(pf, pos, symbol, side, qty=fill.quantity, price=fill.price,
                asset_type=rec.asset_type, multiplier=multiplier)

    trade = Trade(
        portfolio_id=pf.id,
        recommendation_id=recommendation_id,
        symbol=symbol,
        asset_type=rec.asset_type,
        side=side,
        quantity=_dec(fill.quantity),
        price=_dec(fill.price),
        alpaca_order_id=fill.order_id,
        status=fill.status,
    )
    db.add(trade)
    db.commit()
    db.refresh(trade)
    logger.info("paper %s %s x%.4f @ %.2f in portfolio %s (provider=%s)",
                side, symbol, fill.quantity, fill.price, pf.id, execution.name)
    return trade


def _accept_via_alpaca(
    db: Session, pf: Portfolio, rec: Recommendation, recommendation_id: UUID,
    symbol: str, side: str, is_option: bool, quantity: float | None,
    override_price: float | None, price_source: PriceDataSource, broker,
) -> Trade:
    """Submit a real Alpaca paper order, then mirror the account into the portfolio."""
    if is_option:
        raise TradeRejected(
            "Options paper trading isn't supported on Alpaca-linked portfolios — "
            "use a simulated portfolio for options."
        )
    _sync_from_alpaca(db, pf, broker)  # fresh cash/positions before sizing

    price = override_price or (float(rec.entry_target) if rec.entry_target else None)
    if not price or price <= 0:
        price = _latest_price(price_source, symbol)
    pos = next((p for p in pf.positions if p.symbol == symbol), None)
    qty = _resolve_quantity(quantity, rec, side, price, pf, pos, 1, False)

    try:
        fill = broker.submit_order(
            OrderRequest(symbol=symbol, side=side, quantity=qty, asset_type="stock"),
            reference_price=price,
        )
    except ExecutionError as exc:
        raise TradeRejected(f"Alpaca order rejected: {exc}") from exc
    trade = Trade(
        portfolio_id=pf.id, recommendation_id=recommendation_id, symbol=symbol,
        asset_type="stock", side=side, quantity=_dec(fill.quantity),
        price=_dec(fill.price), alpaca_order_id=fill.order_id, status=fill.status,
    )
    db.add(trade)
    db.commit()
    _sync_from_alpaca(db, pf, broker)  # reflect the new fill (or pending order)
    db.refresh(trade)
    logger.info("alpaca paper %s %s x%.4f in portfolio %s (status=%s)",
                side, symbol, fill.quantity, pf.id, fill.status)
    return trade


def _resolve_quantity(
    quantity: float | None, rec: Recommendation, side: str, price: float,
    pf: Portfolio, pos: Position | None, multiplier: int, is_option: bool,
) -> float:
    if quantity is not None:
        qty = float(quantity)
    elif rec.position_size:
        qty = float(rec.position_size)
    elif side == "buy" and is_option:
        qty = 1.0  # one contract by default
    elif side == "buy":
        total_value = float(pf.cash_balance) + _positions_value(pf)
        sizing = position_size(
            price, total_value,
            stop_loss=float(rec.stop_loss) if rec.stop_loss else None,
            cash_available=float(pf.cash_balance),
        )
        qty = max(1.0, sizing["shares"])
    else:  # sell with no explicit qty -> close the position
        qty = float(pos.quantity) if pos else 0.0

    if side == "buy":
        affordable = float(pf.cash_balance) // (price * multiplier)  # whole units
        qty = min(float(int(qty)), affordable)
        if qty <= 0:
            raise TradeRejected("Insufficient cash for even one unit")
    else:
        held = float(pos.quantity) if pos else 0.0
        if held <= 0:
            raise TradeRejected(f"No position in {rec.symbol} to sell")
        qty = min(float(int(qty)) if qty >= 1 else qty, held)
        if qty <= 0:
            raise TradeRejected("Sell quantity resolves to zero")
    return qty


def _apply_fill(
    pf: Portfolio, pos: Position | None, symbol: str, side: str,
    qty: float, price: float, asset_type: str, multiplier: int,
) -> None:
    if side == "buy":
        pf.cash_balance = _dec(float(pf.cash_balance) - qty * price * multiplier)
        if pos is None:
            pf.positions.append(Position(
                symbol=symbol, asset_type=asset_type, quantity=_dec(qty),
                avg_cost=_dec(price), current_price=_dec(price), unrealized_pl=_dec(0),
            ))
        else:
            old_qty, old_avg = float(pos.quantity), float(pos.avg_cost)
            new_qty = old_qty + qty
            new_avg = (old_qty * old_avg + qty * price) / new_qty
            pos.quantity = _dec(new_qty)
            pos.avg_cost = _dec(new_avg)
            pos.current_price = _dec(price)
            pos.unrealized_pl = _dec((price - new_avg) * new_qty * multiplier)
    else:  # sell — pos is guaranteed by _resolve_quantity
        pf.cash_balance = _dec(float(pf.cash_balance) + qty * price * multiplier)
        remaining = float(pos.quantity) - qty
        if remaining <= 1e-9:
            pf.positions.remove(pos)  # delete-orphan cascade removes the row
        else:
            pos.quantity = _dec(remaining)
            pos.current_price = _dec(price)
            pos.unrealized_pl = _dec((price - float(pos.avg_cost)) * remaining * multiplier)


# ---- read models ----------------------------------------------------------

def positions_out(pf: Portfolio) -> list[PositionOut]:
    total = float(pf.cash_balance) + _positions_value(pf)
    out: list[PositionOut] = []
    for p in pf.positions:
        price, avg = float(p.current_price), float(p.avg_cost)
        mv = _market_value(p)
        out.append(PositionOut(
            id=p.id, symbol=p.symbol, asset_type=p.asset_type,
            quantity=float(p.quantity), avg_cost=avg, current_price=price,
            market_value=round(mv, 2),
            unrealized_pl=float(p.unrealized_pl),
            unrealized_pct=round((price - avg) / avg * 100.0, 2) if avg else 0.0,
            weight_pct=round(mv / total * 100.0, 2) if total else 0.0,
        ))
    return out


def trades_out(pf: Portfolio) -> list[TradeOut]:
    return [
        TradeOut(
            id=t.id, symbol=t.symbol, asset_type=t.asset_type, side=t.side,
            quantity=float(t.quantity), price=float(t.price), status=t.status,
            recommendation_id=t.recommendation_id, executed_at=t.executed_at,
        )
        for t in pf.trades
    ]


def summarize(
    db: Session, pf: Portfolio, price_source: PriceDataSource, broker=None
) -> PortfolioSummary:
    sync_portfolio_state(db, pf, price_source, broker)
    cash = float(pf.cash_balance)
    positions_value = _positions_value(pf)
    total_value = cash + positions_value
    holdings = [HoldingExposure(p.symbol, _market_value(p)) for p in pf.positions]
    risk = portfolio_risk_metrics(holdings, cash, total_value)
    return PortfolioSummary(
        id=pf.id, name=pf.name, cash_balance=round(cash, 2),
        positions_value=round(positions_value, 2), total_value=round(total_value, 2),
        total_unrealized_pl=round(sum(float(p.unrealized_pl) for p in pf.positions), 2),
        total_pl=round(total_value - float(pf.starting_cash), 2),
        num_positions=len(pf.positions), risk=risk,
    )


def allocation(pf: Portfolio) -> AllocationOut:
    total = _positions_value(pf)
    by_symbol: list[AllocationSlice] = []
    by_type: dict[str, float] = {}
    for p in pf.positions:
        mv = _market_value(p)
        by_symbol.append(AllocationSlice(
            label=p.symbol, value=round(mv, 2),
            pct=round(mv / total * 100.0, 2) if total else 0.0,
        ))
        by_type[p.asset_type] = by_type.get(p.asset_type, 0.0) + mv
    by_asset_type = [
        AllocationSlice(label=k, value=round(v, 2),
                        pct=round(v / total * 100.0, 2) if total else 0.0)
        for k, v in by_type.items()
    ]
    return AllocationOut(by_symbol=by_symbol, by_asset_type=by_asset_type)


def review_holdings(
    db: Session, pf: Portfolio, price_source: PriceDataSource, broker=None
) -> ReviewResponse:
    """Run the Holdings Review agent on each position + portfolio risk metrics."""
    sync_portfolio_state(db, pf, price_source, broker)
    cash = float(pf.cash_balance)
    total_value = cash + _positions_value(pf)
    reviews: list[HoldingReviewItem] = []
    for p in pf.positions:
        view = PositionView(
            symbol=p.symbol, quantity=float(p.quantity), avg_cost=float(p.avg_cost),
            current_price=float(p.current_price), portfolio_value=total_value,
        )
        r = run_holdings_review(view, asset_type=p.asset_type)
        reviews.append(HoldingReviewItem(
            symbol=p.symbol, action=r.action, unrealized_pct=r.unrealized_pct,
            position_risk_score=r.position_risk_score,
            concentration_flags=r.concentration_flags,
            rebalancing_suggestions=r.rebalancing_suggestions, reasoning=r.reasoning,
        ))
    holdings = [HoldingExposure(p.symbol, _market_value(p)) for p in pf.positions]
    return ReviewResponse(
        portfolio_id=pf.id, reviews=reviews,
        risk=portfolio_risk_metrics(holdings, cash, total_value),
    )
