"""create alpaca_credentials (per-user Alpaca keys)

Revision ID: 0008_alpaca_credentials
Revises: 0007_widen_trade_status
Create Date: 2026-06-08
"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0008_alpaca_credentials"
down_revision: str | None = "0007_widen_trade_status"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "alpaca_credentials",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False,
                  unique=True),
        sa.Column("api_key", sa.String(64), nullable=False),
        sa.Column("secret_encrypted", sa.Text, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_alpaca_credentials_user_id", "alpaca_credentials", ["user_id"],
                    unique=True)


def downgrade() -> None:
    op.drop_index("ix_alpaca_credentials_user_id", table_name="alpaca_credentials")
    op.drop_table("alpaca_credentials")
