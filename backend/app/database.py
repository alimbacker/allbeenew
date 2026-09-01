"""SQLAlchemy engine and session plumbing.

The app targets PostgreSQL (+pgvector). SQLite is supported as a fallback so the
test suite and a first-run developer machine work without a database server;
the vector search service transparently switches strategy based on the dialect.
"""

from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings

_connect_args: dict = {}
_kwargs: dict = {"pool_pre_ping": True, "future": True}

if settings.database_url.startswith("sqlite"):
    _connect_args = {"check_same_thread": False}
    _kwargs.pop("pool_pre_ping")

engine = create_engine(settings.database_url, connect_args=_connect_args, **_kwargs)

if settings.database_url.startswith("sqlite"):

    @event.listens_for(engine, "connect")
    def _sqlite_pragmas(dbapi_connection, _):  # pragma: no cover - trivial
        cur = dbapi_connection.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()


SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


def get_db() -> Iterator[Session]:
    """FastAPI dependency yielding a request-scoped session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def session_scope() -> Session:
    """Session for code running outside a request (workers, scripts, seeds)."""
    return SessionLocal()
