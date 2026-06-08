"""Backtesting routes (docs/05-api-spec.md). All routes require auth."""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from app.api.deps import CurrentUser, DbSession
from app.models.backtest import Backtest
from app.schemas.backtest import (
    BacktestOut,
    BacktestRequest,
    BacktestSummary,
    CompareItem,
    CompareRequest,
    CompareResponse,
)
from app.services.backtesting.runner import BacktestError, run_and_store
from app.services.backtesting.strategies import STRATEGY_LABELS
from app.services.data_sources.base import PriceDataSource
from app.services.data_sources.yfinance_source import YFinancePriceSource

router = APIRouter(prefix="/backtests", tags=["backtesting"])


def get_price_source() -> PriceDataSource:
    """Indirection point so tests can swap in a fake price source."""
    return YFinancePriceSource()


def _label(strategy: str) -> str:
    return STRATEGY_LABELS.get(strategy, strategy)


def _to_out(bt: Backtest) -> BacktestOut:
    return BacktestOut(
        id=bt.id, strategy=bt.strategy, strategy_label=_label(bt.strategy),
        symbol=bt.symbol, benchmark=bt.benchmark, horizon=bt.horizon,
        start_date=bt.start_date, end_date=bt.end_date, metrics=bt.metrics,
        equity_curve=bt.equity_curve, created_at=bt.created_at,
    )


def _owned(db, user, backtest_id: UUID) -> Backtest:
    bt = db.get(Backtest, backtest_id)
    if bt is None or bt.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Backtest not found")
    return bt


@router.post("", status_code=status.HTTP_201_CREATED, response_model=BacktestOut)
def create_backtest(body: BacktestRequest, db: DbSession, user: CurrentUser) -> BacktestOut:
    try:
        bt = run_and_store(db, user, body, get_price_source())
    except BacktestError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc
    return _to_out(bt)


@router.get("", response_model=list[BacktestSummary])
def list_backtests(db: DbSession, user: CurrentUser) -> list[BacktestSummary]:
    rows = (
        db.query(Backtest)
        .filter(Backtest.user_id == user.id)
        .order_by(Backtest.created_at.desc())
        .all()
    )
    return [
        BacktestSummary(
            id=bt.id, strategy=bt.strategy, strategy_label=_label(bt.strategy),
            symbol=bt.symbol, benchmark=bt.benchmark, horizon=bt.horizon,
            metrics=bt.metrics, created_at=bt.created_at,
        )
        for bt in rows
    ]


@router.get("/{backtest_id}", response_model=BacktestOut)
def get_backtest(backtest_id: UUID, db: DbSession, user: CurrentUser) -> BacktestOut:
    return _to_out(_owned(db, user, backtest_id))


@router.post("/compare", response_model=CompareResponse)
def compare_backtests(
    body: CompareRequest, db: DbSession, user: CurrentUser
) -> CompareResponse:
    items = []
    for bid in body.backtest_ids:
        bt = _owned(db, user, bid)
        items.append(CompareItem(
            id=bt.id, strategy=bt.strategy, strategy_label=_label(bt.strategy),
            symbol=bt.symbol, metrics=bt.metrics,
        ))
    return CompareResponse(items=items)
