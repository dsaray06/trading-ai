"""add portfolios.broker (Phase: Alpaca integration)

Revision ID: 0006_portfolio_broker
Revises: 0005_backtests
Create Date: 2026-06-08
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0006_portfolio_broker"
down_revision: str | None = "0005_backtests"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "portfolios",
        sa.Column("broker", sa.String(16), nullable=False, server_default="simulated"),
    )


def downgrade() -> None:
    op.drop_column("portfolios", "broker")
