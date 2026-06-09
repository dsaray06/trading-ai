"""Portfolio routes (docs/05-api-spec.md). All routes require auth.

Handlers stay thin: resolve the owned portfolio, delegate to the portfolio
service, map service errors to HTTP status codes.
"""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from app.api.deps import CurrentUser, DbSession
from app.models.portfolio import Portfolio
from app.models.user import User
from app.schemas.portfolio import (
    AcceptTradeRequest,
    AllocationOut,
    PortfolioCreate,
    PortfolioOut,
    PortfolioSummary,
    PositionOut,
    ReviewResponse,
    TradeOut,
    TradePreview,
)
from app.services import alpaca_credentials as creds
from app.services import market_data
from app.services import portfolio as svc
from app.services.data_sources.base import PriceDataSource
from app.services.data_sources.yfinance_source import YFinancePriceSource

router = APIRouter(prefix="/portfolios", tags=["portfolio"])


def get_price_source() -> PriceDataSource:
    """Indirection point so tests can swap in a fake price source."""
    return YFinancePriceSource()


def _price_source(db, user: User) -> PriceDataSource:
    """Alpaca-backed pricing (works on cloud IPs) when keys are available, else
    the test/local seam. yfinance's price endpoint is blocked from Render."""
    if market_data.alpaca_data_creds(db, user):
        return market_data.price_source_for(db, user)
    return get_price_source()


def user_alpaca_broker(db, user: User):
    """The calling user's own Alpaca broker, or None. Indirection point for tests."""
    return creds.broker_for_user(db, user)


def _broker_for(pf: Portfolio, db, user: User):
    """The broker needed to sync this portfolio (the user's Alpaca broker, or None)."""
    return user_alpaca_broker(db, user) if pf.broker == "alpaca" else None


def _portfolio_out(pf: Portfolio) -> PortfolioOut:
    return PortfolioOut(
        id=pf.id, name=pf.name, broker=pf.broker, starting_cash=float(pf.starting_cash),
        cash_balance=float(pf.cash_balance), created_at=pf.created_at,
    )


def _owned(db, user, portfolio_id: UUID) -> Portfolio:
    try:
        return svc.get_owned_portfolio(db, user, portfolio_id)
    except svc.NotFound as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    except svc.Forbidden as exc:
        raise HTTPException(status.HTTP_403_FORBIDDEN, str(exc)) from exc


@router.get("", response_model=list[PortfolioOut])
def list_portfolios(db: DbSession, user: CurrentUser) -> list[PortfolioOut]:
    return [_portfolio_out(p) for p in svc.list_portfolios(db, user)]


@router.post("", status_code=status.HTTP_201_CREATED, response_model=PortfolioOut)
def create_portfolio(body: PortfolioCreate, db: DbSession, user: CurrentUser) -> PortfolioOut:
    alpaca = user_alpaca_broker(db, user) if body.broker == "alpaca" else None
    if body.broker == "alpaca" and alpaca is None:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Connect your Alpaca account first (Settings → Connect Alpaca).",
        )
    try:
        pf = svc.create_portfolio(
            db, user, body.name, body.starting_cash, body.broker, alpaca
        )
    except svc.PortfolioError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc
    return _portfolio_out(pf)


@router.get("/{portfolio_id}", response_model=PortfolioSummary)
def get_portfolio(portfolio_id: UUID, db: DbSession, user: CurrentUser) -> PortfolioSummary:
    pf = _owned(db, user, portfolio_id)
    return svc.summarize(db, pf, _price_source(db, user), _broker_for(pf, db, user))


@router.get("/{portfolio_id}/positions", response_model=list[PositionOut])
def get_positions(portfolio_id: UUID, db: DbSession, user: CurrentUser) -> list[PositionOut]:
    pf = _owned(db, user, portfolio_id)
    svc.sync_portfolio_state(db, pf, _price_source(db, user), _broker_for(pf, db, user))
    return svc.positions_out(pf)


@router.get("/{portfolio_id}/allocation", response_model=AllocationOut)
def get_allocation(portfolio_id: UUID, db: DbSession, user: CurrentUser) -> AllocationOut:
    pf = _owned(db, user, portfolio_id)
    svc.sync_portfolio_state(db, pf, _price_source(db, user), _broker_for(pf, db, user))
    return svc.allocation(pf)


@router.get("/{portfolio_id}/trades", response_model=list[TradeOut])
def get_trades(portfolio_id: UUID, db: DbSession, user: CurrentUser) -> list[TradeOut]:
    pf = _owned(db, user, portfolio_id)
    return svc.trades_out(pf)


@router.post("/{portfolio_id}/trades", status_code=status.HTTP_201_CREATED,
             response_model=TradeOut)
def accept_trade(
    portfolio_id: UUID, body: AcceptTradeRequest, db: DbSession, user: CurrentUser
) -> TradeOut:
    pf = _owned(db, user, portfolio_id)
    price_source = _price_source(db, user)
    if pf.broker == "alpaca":
        execution = user_alpaca_broker(db, user)
        if execution is None:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY,
                                "Connect your Alpaca account first.")
    else:
        execution = svc.SimulatedExecution(price_source)
    try:
        trade = svc.accept_recommendation(
            db, pf, body.recommendation_id, body.quantity, body.override_price,
            price_source, execution,
        )
    except svc.NotFound as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    except svc.TradeRejected as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc
    except svc.PortfolioError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc
    return TradeOut(
        id=trade.id, symbol=trade.symbol, asset_type=trade.asset_type, side=trade.side,
        quantity=float(trade.quantity), price=float(trade.price), status=trade.status,
        recommendation_id=trade.recommendation_id, executed_at=trade.executed_at,
    )


@router.get("/{portfolio_id}/trades/preview/{recommendation_id}", response_model=TradePreview)
def preview_trade(
    portfolio_id: UUID, recommendation_id: UUID, db: DbSession, user: CurrentUser
) -> TradePreview:
    """Auto-sized preview of a paper trade (suggested quantity, cost, weight)."""
    pf = _owned(db, user, portfolio_id)
    try:
        preview = svc.preview_trade(
            db, pf, recommendation_id, _price_source(db, user), _broker_for(pf, db, user)
        )
    except svc.NotFound as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    except (svc.TradeRejected, svc.PortfolioError) as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc
    return TradePreview(**preview)


@router.post("/{portfolio_id}/sync", response_model=PortfolioSummary)
def sync_portfolio(portfolio_id: UUID, db: DbSession, user: CurrentUser) -> PortfolioSummary:
    pf = _owned(db, user, portfolio_id)
    return svc.summarize(db, pf, _price_source(db, user), _broker_for(pf, db, user))


@router.post("/{portfolio_id}/review", response_model=ReviewResponse)
def review_portfolio(portfolio_id: UUID, db: DbSession, user: CurrentUser) -> ReviewResponse:
    pf = _owned(db, user, portfolio_id)
    return svc.review_holdings(db, pf, _price_source(db, user), _broker_for(pf, db, user))
