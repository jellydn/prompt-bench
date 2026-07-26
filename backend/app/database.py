import logging

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from sqlalchemy.pool import NullPool, QueuePool

from .config import settings

logger = logging.getLogger(__name__)

# PromptBench is designed for PostgreSQL in production.
# SQLite is supported for local development only and will not handle
# concurrent writes safely. Use the Docker Compose stack for any
# multi-user or concurrent-access deployment.
_SQLITE_WARNING = (
    "Using SQLite database — this is suitable for development only. "
    "For production, use PostgreSQL (see docker-compose.yml)."
)


class Base(DeclarativeBase):
    pass


_engine_url = settings.database_url
# Normalize postgresql:// → postgresql+psycopg:// for psycopg v3 driver support
if _engine_url.startswith("postgresql://") and "+psycopg" not in _engine_url:
    _engine_url = _engine_url.replace("postgresql://", "postgresql+psycopg://", 1)

if _engine_url.startswith("sqlite"):
    logger.warning(_SQLITE_WARNING)
    connect_args = {"check_same_thread": False}
    engine = create_engine(
        _engine_url,
        connect_args=connect_args,
        poolclass=NullPool,
    )
else:
    # PostgreSQL with explicit connection pooling
    connect_args = {}
    engine = create_engine(
        _engine_url,
        connect_args=connect_args,
        poolclass=QueuePool,
        pool_size=settings.database_pool_size,
        max_overflow=settings.database_max_overflow,
        pool_pre_ping=True,
    )

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    from . import models  # noqa: F401, PLC0415

    Base.metadata.create_all(bind=engine)
