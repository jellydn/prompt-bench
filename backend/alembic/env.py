"""Alembic migration environment for PromptBench backend."""

import os
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

from alembic import context

# Alembic Config
config = context.config

# Set up logging from alembic.ini
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Import the model Base without triggering app.database engine creation
from app.models import Base  # noqa: E402

target_metadata = Base.metadata


def get_url() -> str:
    """Get the database URL, preferring DATABASE_URL from the environment.

    Priority: DATABASE_URL > ALEMBIC_TEST_URL > alembic.ini value.
    This ensures migrations use the same database as the running app.
    """
    url = os.environ.get("DATABASE_URL") or os.environ.get("ALEMBIC_TEST_URL")
    if url:
        # Normalize postgres:// driver prefix for psycopg v3 (same as app.database)
        if url.startswith("postgres://") and "+psycopg" not in url:
            url = url.replace("postgres://", "postgresql+psycopg://", 1)
        elif url.startswith("postgresql://") and "+psycopg" not in url:
            url = url.replace("postgresql://", "postgresql+psycopg://", 1)
        return url
    return config.get_main_option("sqlalchemy.url")


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode (emit SQL without DB connection)."""
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode (connect to live DB)."""
    url = get_url()
    cfg = config.get_section(config.config_ini_section, {})
    cfg["sqlalchemy.url"] = url
    connectable = engine_from_config(cfg, prefix="sqlalchemy.", poolclass=pool.NullPool)
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
