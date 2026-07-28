"""add cache metrics to benchmark_results

Revision ID: 0002_cache_metrics
Revises: 2dae871076fe
Create Date: 2026-07-27 00:00:00.000000

The migration is idempotent: each column is added in its own transaction
wrapped in try/except so it safely passes on a fresh database where
init_db() already created the columns via create_all().
"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.exc import OperationalError

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0002_cache_metrics"
down_revision: str | Sequence[str] | None = "2dae871076fe"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_COLUMNS: list[tuple[str, sa.types.TypeEngine, bool]] = [
    ("cache_hit", sa.Boolean(), True),
    ("cache_type", sa.String(length=20), True),
    ("cache_lookup_ms", sa.Integer(), True),
    ("provider_latency_ms", sa.Integer(), True),
]


def upgrade() -> None:
    """Add cache metric columns to benchmark_results (idempotent).

    Each column is added in its own batch transaction.  If a column
    already exists (e.g. because init_db() ran first on a fresh DB),
    the OperationalError is caught and logged — the migration
    continues to the next column.
    """
    for col_name, col_type, nullable in _COLUMNS:
        try:
            with op.batch_alter_table("benchmark_results") as batch_op:
                batch_op.add_column(
                    sa.Column(col_name, col_type, nullable=nullable)
                )
        except OperationalError:
            # Column already exists — init_db() created it before Alembic ran.
            pass


def downgrade() -> None:
    """Remove cache metric columns from benchmark_results."""
    columns = [c[0] for c in _COLUMNS]
    with op.batch_alter_table("benchmark_results") as batch_op:
        for col_name in reversed(columns):
            batch_op.drop_column(col_name)
