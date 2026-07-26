from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .config import settings


class Base(DeclarativeBase):
    pass


_engine_url = settings.database_url
# Normalize postgresql:// → postgresql+psycopg:// for psycopg v3 driver support
if _engine_url.startswith("postgresql://") and "+psycopg" not in _engine_url:
    _engine_url = _engine_url.replace("postgresql://", "postgresql+psycopg://", 1)

connect_args = {"check_same_thread": False} if _engine_url.startswith("sqlite") else {}
engine = create_engine(_engine_url, connect_args=connect_args)
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
