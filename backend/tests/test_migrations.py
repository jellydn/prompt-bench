"""Tests for database migrations with Alembic."""

import os
import pathlib
import tempfile

from alembic.command import downgrade, upgrade
from alembic.config import Config
from sqlalchemy import create_engine, text


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
