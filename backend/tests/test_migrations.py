"""Tests for database migrations with Alembic."""

import contextlib
import os
import pathlib
import tempfile
from datetime import UTC, datetime

from alembic.command import downgrade, upgrade
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.pool import NullPool


def test_alembic_config_exists():
    """Alembic configuration should be present."""
    assert pathlib.Path("alembic.ini").exists()
    assert pathlib.Path("alembic").is_dir()
    assert pathlib.Path("alembic/env.py").exists()
    versions = list(pathlib.Path("alembic/versions").glob("*.py"))
    assert len(versions) >= 1, "At least one migration should exist"


def test_migration_full_cycle():
    """Full upgrade/downgrade cycle on a temporary database."""
    with tempfile.NamedTemporaryFile(suffix=".test.db", delete=False) as f:
        db_path = f.name
        db_url = f"sqlite:///{db_path}"

    alembic_cfg = Config("alembic.ini")

    try:
        os.environ["ALEMBIC_TEST_URL"] = db_url
        upgrade(alembic_cfg, "head")

        # Verify tables exist after upgrade
        engine = create_engine(db_url, connect_args={"check_same_thread": False})
        with engine.connect() as conn:
            tables = {
                row[0]
                for row in conn.execute(
                    text("SELECT name FROM sqlite_master WHERE type='table'")
                ).all()
            }
            assert "benchmarks" in tables, f"Tables found: {tables}"
            assert "benchmark_results" in tables
            assert "alembic_version" in tables

        # Downgrade to base
        downgrade(alembic_cfg, "base")

        # Verify tables dropped after downgrade
        with engine.connect() as conn:
            tables_after = {
                row[0]
                for row in conn.execute(
                    text("SELECT name FROM sqlite_master WHERE type='table'")
                ).all()
            }
            assert "benchmarks" not in tables_after
            assert "benchmark_results" not in tables_after

    finally:
        engine.dispose()
        os.unlink(db_path)
        os.environ.pop("ALEMBIC_TEST_URL", None)


def test_downgrade_preserves_non_cache_data():  # noqa: PLR0915

    """Downgrade from 0002→0001 should drop cache columns but keep other data.

    On PostgreSQL, batch_alter_table creates a temp table, copies data,
    drops the old table, and renames.  This test verifies that the
    copy-rename cycle preserves non-cache columns (id, benchmark_id,
    provider, model, etc.) and that re-upgrading restores the cache
    columns as nullable.
    """
    with tempfile.NamedTemporaryFile(suffix=".test.db", delete=False) as f:
        db_path = f.name
        db_url = f"sqlite:///{db_path}"

    alembic_cfg = Config("alembic.ini")
    now = datetime.now(UTC)

    try:
        os.environ["ALEMBIC_TEST_URL"] = db_url

        # Enable WAL journal mode so alembic and the test engine can
        # access the same SQLite database concurrently.
        _init = create_engine(db_url)
        with _init.connect() as c:
            c.execute(text("PRAGMA journal_mode=WAL"))
            c.commit()
        _init.dispose()

        # ── 1. Upgrade to head (includes cache columns) ──────────────
        upgrade(alembic_cfg, "head")
        # NullPool forces full connection close after each with-block exit,
        # avoiding SQLite write-lock contention with alembic's own engine.
        engine = create_engine(
            db_url,
            connect_args={"check_same_thread": False},
            poolclass=NullPool,
        )

        # ── 2. Insert a benchmark + result row with cache column values
        # ORM-level defaults (temperature=0.7, max_tokens=1000,
        # created_at=utcnow) do not translate to SQL DEFAULT when the
        # migration schema was generated from create_all, so we provide
        # every NOT NULL column explicitly.
        with engine.connect() as conn:
            conn.execute(
                text(
                    "INSERT INTO benchmarks "
                    "(prompt, system_prompt, temperature, max_tokens, status, created_at) "
                    "VALUES ('test prompt', '', 0.0, 10, 'completed', :now)"
                ),
                {"now": now},
            )
            conn.execute(
                text(
                    "INSERT INTO benchmark_results "
                    "(benchmark_id, provider, model, input_tokens, output_tokens, "
                    "ttft_ms, total_latency_ms, cost, cache_hit, cache_type, "
                    "cache_lookup_ms, provider_latency_ms, created_at) "
                    "VALUES (1, 'openai', 'gpt-4o-mini', 100, 50, 200, 500, "
                    "0.005, 1, 'response', 2, 480, :now)"
                ),
                {"now": now},
            )
            conn.commit()

        # ── 3. Downgrade to just before 0002 (drops cache columns) ───
        downgrade(alembic_cfg, "2dae871076fe")

        # ── 4. Verify non-cache data survived the downgrade ──────────
        with engine.connect() as conn:
            row = conn.execute(
                text(
                    "SELECT id, benchmark_id, provider, model, "
                    "input_tokens, output_tokens, ttft_ms, total_latency_ms, cost "
                    "FROM benchmark_results WHERE id = 1"
                )
            ).first()
            assert row is not None, "Row should survive downgrade"
            assert row.benchmark_id == 1
            assert row.provider == "openai"
            assert row.model == "gpt-4o-mini"
            assert row.input_tokens == 100
            assert row.output_tokens == 50
            assert row.ttft_ms == 200
            assert row.total_latency_ms == 500
            assert row.cost == 0.005

            # Cache columns should no longer exist after downgrade.
            result = conn.execute(text("SELECT * FROM benchmark_results LIMIT 1"))
            col_names = set(result.keys())
            assert "cache_hit" not in col_names
            assert "cache_type" not in col_names
            assert "cache_lookup_ms" not in col_names
            assert "provider_latency_ms" not in col_names

        # ── 5. Re-upgrade — cache columns should return (NULL) ───────
        upgrade(alembic_cfg, "head")
        # Re-create engine with NullPool for final verification reads.
        engine = create_engine(
            db_url,
            connect_args={"check_same_thread": False},
            poolclass=NullPool,
        )
        with engine.connect() as conn:
            row = conn.execute(
                text(
                    "SELECT id, benchmark_id, provider, model, "
                    "cache_hit, cache_type, cache_lookup_ms, provider_latency_ms "
                    "FROM benchmark_results WHERE id = 1"
                )
            ).first()
            assert row is not None, "Row should still exist after re-upgrade"
            # Non-cache data still intact.
            assert row.provider == "openai"
            assert row.model == "gpt-4o-mini"
            # Cache columns restored as NULL (data is gone — expected).
            assert row.cache_hit is None
            assert row.cache_type is None
            assert row.cache_lookup_ms is None
            assert row.provider_latency_ms is None

    finally:
        engine.dispose()
        os.unlink(db_path)
        # WAL journal sidecars (created by PRAGMA journal_mode=WAL).
        with contextlib.suppress(OSError):
            os.unlink(db_path + "-wal")
        with contextlib.suppress(OSError):
            os.unlink(db_path + "-shm")
        os.environ.pop("ALEMBIC_TEST_URL", None)
