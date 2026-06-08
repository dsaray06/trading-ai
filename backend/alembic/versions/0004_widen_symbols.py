"""widen symbol columns to 32 for option contract symbols (Phase 4)

Revision ID: 0004_widen_symbols
Revises: 0003_users_portfolios
Create Date: 2026-06-08
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0004_widen_symbols"
down_revision: str | None = "0003_users_portfolios"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    for table in ("recommendations", "positions", "trades"):
        op.alter_column(table, "symbol", type_=sa.String(32), existing_type=sa.String(16))


def downgrade() -> None:
    for table in ("recommendations", "positions", "trades"):
        op.alter_column(table, "symbol", type_=sa.String(16), existing_type=sa.String(32))
