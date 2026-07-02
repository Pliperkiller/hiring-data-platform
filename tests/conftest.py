"""Shared test fixtures: a migrated test database and per-test session isolation.

Integration tests require DATABASE_URL pointing at a reachable Postgres. CI provisions one
as a service container (see .github/workflows/ci.yml); locally, run
`docker compose up -d db` and export DATABASE_URL for a matching `hiring_test` database.
"""

import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.infrastructure.db.session import build_engine, build_sessionmaker

TEST_DATABASE_URL = os.environ.get(
    "DATABASE_URL", "postgresql+psycopg://hiring:hiring@localhost:5432/hiring_test"
)
REPO_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="session")
def engine() -> Iterator[Engine]:
    eng = build_engine(TEST_DATABASE_URL)
    yield eng
    eng.dispose()


@pytest.fixture(scope="session")
def apply_migrations(engine: Engine) -> None:
    os.environ["DATABASE_URL"] = TEST_DATABASE_URL
    config = Config(str(REPO_ROOT / "alembic.ini"))
    command.upgrade(config, "head")


@pytest.fixture
def db_session(engine: Engine, apply_migrations: None) -> Iterator[Session]:
    connection = engine.connect()
    transaction = connection.begin()
    session_factory = build_sessionmaker(engine)
    session = session_factory(bind=connection)

    yield session

    session.close()
    if transaction.is_active:
        transaction.rollback()
    connection.close()
