"""create users, portfolios, positions, trades (Phase 3)

Revision ID: 0003_users_portfolios
Revises: 0002_recommendations
Create Date: 2026-06-08
"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0003_users_portfolios"
down_revision: str | None = "0002_recommendations"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _ts(*extra):
    return (
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        *extra,
    )


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(320), nullable=False, unique=True),
        sa.Column("hashed_password", sa.Text, nullable=True),
        sa.Column("oauth_provider", sa.String(32), nullable=True),
        sa.Column("oauth_subject", sa.String(255), nullable=True),
        *_ts(),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "portfolios",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("starting_cash", sa.Numeric(18, 2), nullable=False),
        sa.Column("cash_balance", sa.Numeric(18, 2), nullable=False),
        sa.Column("alpaca_account_id", sa.String(64), nullable=True),
        *_ts(),
    )
    op.create_index("ix_portfolios_user_id", "portfolios", ["user_id"])

    op.create_table(
        "positions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("portfolio_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("portfolios.id", ondelete="CASCADE"), nullable=False),
        sa.Column("symbol", sa.String(16), nullable=False),
        sa.Column("asset_type", sa.String(16), nullable=False, server_default="stock"),
        sa.Column("quantity", sa.Numeric(18, 4), nullable=False),
        sa.Column("avg_cost", sa.Numeric(18, 4), nullable=False),
        sa.Column("current_price", sa.Numeric(18, 4), nullable=False),
        sa.Column("unrealized_pl", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("opened_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        *_ts(),
    )
    op.create_index("ix_positions_portfolio_id", "positions", ["portfolio_id"])
    op.create_index("ix_positions_symbol", "positions", ["symbol"])

    op.create_table(
        "trades",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("portfolio_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("portfolios.id", ondelete="CASCADE"), nullable=False),
        sa.Column("recommendation_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("recommendations.id", ondelete="SET NULL"), nullable=True),
        sa.Column("symbol", sa.String(16), nullable=False),
        sa.Column("asset_type", sa.String(16), nullable=False, server_default="stock"),
        sa.Column("side", sa.String(8), nullable=False),
        sa.Column("quantity", sa.Numeric(18, 4), nullable=False),
        sa.Column("price", sa.Numeric(18, 4), nullable=False),
        sa.Column("alpaca_order_id", sa.String(64), nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="filled"),
        sa.Column("executed_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        *_ts(),
    )
    op.create_index("ix_trades_portfolio_id", "trades", ["portfolio_id"])
    op.create_index("ix_trades_symbol", "trades", ["symbol"])
    op.create_index("ix_trades_recommendation_id", "trades", ["recommendation_id"])
    # Idempotency: a broker order id maps to at most one trade.
    op.create_index(
        "uq_trades_alpaca_order_id", "trades", ["alpaca_order_id"], unique=True,
        postgresql_where=sa.text("alpaca_order_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_table("trades")
    op.drop_table("positions")
    op.drop_table("portfolios")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
