"""baseline (empty)

Phase 0 baseline. Intentionally empty — establishes the migration chain so
later phases add tables on top of a known starting point.

Revision ID: 0001_baseline
Revises:
Create Date: 2026-06-08
"""
from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "0001_baseline"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
