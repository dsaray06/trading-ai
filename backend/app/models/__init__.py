"""ORM models package.

Importing this module registers every model on `Base.metadata` so Alembic
autogenerate and `Base.metadata.create_all` see the full schema.
"""
from app.db.base import Base
from app.models.alpaca_credential import AlpacaCredential
from app.models.backtest import Backtest
from app.models.portfolio import Portfolio, Position, Trade
from app.models.recommendation import AgentVoteRow, Recommendation
from app.models.user import User

__all__ = [
    "Base",
    "User",
    "Portfolio",
    "Position",
    "Trade",
    "Recommendation",
    "AgentVoteRow",
    "Backtest",
    "AlpacaCredential",
]
