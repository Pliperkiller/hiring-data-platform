"""FastAPI dependencies: DB session lifecycle."""

from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy.orm import Session

from app.infrastructure.config import get_settings
from app.infrastructure.db.session import build_engine, build_sessionmaker

_engine = build_engine(get_settings().database_url)
_session_local = build_sessionmaker(_engine)


def get_db() -> Iterator[Session]:
    session = _session_local()
    try:
        yield session
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
