"""add cache metrics to benchmark_results

Revision ID: 0002_cache_metrics
Revises: 2dae871076fe
Create Date: 2026-07-27 00:00:00.000000

The migration is idempotent: each column is checked for existence
via SQLAlchemy inspector before attempting to add it.  This avoids
transaction aborts on PostgreSQL where trying to add an existing
column inside an Alembic transaction would poison the whole upgrade.
"""
from collections.abc import Sequence

import sqlalchemy as sa

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


def _column_exists(table: str, column: str) -> bool:
    """Check whether *column* already exists on *table*."""
    inspector = sa.inspect(op.get_bind())
    cols = {c["name"] for c in inspector.get_columns(table)}
    return column in cols


def upgrade() -> None:
    """Add cache metric columns to benchmark_results (idempotent).

    Each column is checked for existence before attempting to add it.
    This avoids transaction aborts on PostgreSQL — trying to add a
    column that already exists inside an Alembic transaction would
    poison the entire upgrade.
    """
    for col_name, col_type, nullable in _COLUMNS:
        if not _column_exists("benchmark_results", col_name):
            with op.batch_alter_table("benchmark_results") as batch_op:
                batch_op.add_column(
                    sa.Column(col_name, col_type, nullable=nullable)
                )


def downgrade() -> None:
    """Remove cache metric columns from benchmark_results."""
    columns = [c[0] for c in _COLUMNS]
    with op.batch_alter_table("benchmark_results") as batch_op:
        for col_name in reversed(columns):
            batch_op.drop_column(col_name)
