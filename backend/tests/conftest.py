"""Shared test fixtures."""
from __future__ import annotations

import os

# Ensure config doesn't pick up a real .env or require secrets during tests, and
# that no test makes a real network call to a keyed data provider.
os.environ.setdefault("ANTHROPIC_API_KEY", "")
os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:///:memory:")
os.environ.setdefault("FINNHUB_API_KEY", "")
os.environ.setdefault("POLYGON_API_KEY", "")
os.environ.setdefault("ALPACA_API_KEY", "")
os.environ.setdefault("ALPACA_API_SECRET", "")

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models import Base


@pytest.fixture
def db_session():
    """In-memory SQLite session with the full schema created via the ORM metadata.

    StaticPool + check_same_thread=False keeps a single shared in-memory
    connection usable across threads (the FastAPI TestClient cleans up the
    connection pool from a worker thread).
    """
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    TestSession = sessionmaker(bind=engine, future=True)
    session = TestSession()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()
