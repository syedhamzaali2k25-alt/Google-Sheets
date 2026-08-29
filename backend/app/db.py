"""Database engine/session setup.

DATABASE_URL should point at Postgres in any real deployment (e.g.
postgresql+psycopg://user:password@host:5432/dbname) — that's what the
Alembic migration in backend/alembic/versions/ is meant to run against.
It defaults to a local SQLite file so the backend and its tests run with
zero setup; SQLite is not a production target here, just a convenience.
"""

import os
from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./dev.db")

_connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=_connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Iterator[Session]:
    """FastAPI dependency: yields a session, always closed after the request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
