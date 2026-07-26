"""Fixtures and test helpers for PromptBench backend tests.

Uses a temporary file-based SQLite to avoid in-memory per-connection isolation.
"""

import contextlib
import os
import tempfile
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base, get_db
from app.main import app

_db_fd, _db_path = tempfile.mkstemp(suffix=".test.db")
_engine = create_engine(f"sqlite:///{_db_path}", connect_args={"check_same_thread": False})
_TestingSessionLocal = sessionmaker(bind=_engine)


@pytest.fixture(autouse=True)
def _create_tables():
    """Create all tables before each test, drop after."""
    Base.metadata.create_all(bind=_engine)
    yield
    Base.metadata.drop_all(bind=_engine)


@pytest.fixture
def db_session(_create_tables) -> Generator:
    """Provide a clean session in the test database."""
    session = _TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client(_create_tables) -> Generator:
    """FastAPI TestClient with test database (per-request sessions)."""

    def _override():
        db = _TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _override
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def pytest_unconfigure():
    """Clean up the temporary database file."""
    Base.metadata.drop_all(bind=_engine)
    _engine.dispose()
    os.close(_db_fd)
    with contextlib.suppress(OSError):
        os.unlink(_db_path)
