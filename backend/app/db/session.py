"""Database engine and session management.

Provides a single engine/sessionmaker built from settings, plus a FastAPI
dependency (`get_db`) that yields a session per request and always closes it.
"""
from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings

_settings = get_settings()

engine = create_engine(
    _settings.database_url,
    pool_pre_ping=True,
    future=True,
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency: yield a session, close it afterward."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
