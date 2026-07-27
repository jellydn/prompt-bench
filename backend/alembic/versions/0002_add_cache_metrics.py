"""add cache metrics to benchmark_results

Revision ID: 0002_cache_metrics
Revises: 2dae871076fe
Create Date: 2026-07-27 00:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0002_cache_metrics"
down_revision: str | Sequence[str] | None = "2dae871076fe"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add cache metric columns to benchmark_results."""
    with op.batch_alter_table("benchmark_results") as batch_op:
        batch_op.add_column(sa.Column("cache_hit", sa.Boolean(), nullable=True))
        batch_op.add_column(sa.Column("cache_type", sa.String(length=20), nullable=True))
        batch_op.add_column(sa.Column("cache_lookup_ms", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("provider_latency_ms", sa.Integer(), nullable=True))


def downgrade() -> None:
    """Remove cache metric columns from benchmark_results."""
    with op.batch_alter_table("benchmark_results") as batch_op:
        batch_op.drop_column("provider_latency_ms")
        batch_op.drop_column("cache_lookup_ms")
        batch_op.drop_column("cache_type")
        batch_op.drop_column("cache_hit")
