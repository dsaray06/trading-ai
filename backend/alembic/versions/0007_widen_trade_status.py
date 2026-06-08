"""widen trades.status to 32 (Alpaca order statuses)

Revision ID: 0007_widen_trade_status
Revises: 0006_portfolio_broker
Create Date: 2026-06-08
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0007_widen_trade_status"
down_revision: str | None = "0006_portfolio_broker"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column("trades", "status", type_=sa.String(32), existing_type=sa.String(16))


def downgrade() -> None:
    op.alter_column("trades", "status", type_=sa.String(16), existing_type=sa.String(32))
