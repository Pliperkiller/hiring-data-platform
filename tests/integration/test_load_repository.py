import pytest
from sqlalchemy.orm import Session

from app.domain.rejected_record import Load
from app.infrastructure.db.repositories import SqlAlchemyLoadRepository

pytestmark = pytest.mark.usefixtures("apply_migrations")


def test_create_persists_and_populates_defaults(db_session: Session) -> None:
    repo = SqlAlchemyLoadRepository(db_session)

    load = repo.create(Load(source="historical"))

    assert load.id is not None
    assert load.started_at is not None
    assert load.accepted == 0
    assert load.rejected == 0
    assert load.finished_at is None


def test_mark_finished_updates_counts_and_finished_at(db_session: Session) -> None:
    repo = SqlAlchemyLoadRepository(db_session)
    load = repo.create(Load(source="api:hired_employees"))
    assert load.id is not None

    updated = repo.mark_finished(load.id, accepted=930, rejected=70)

    assert updated.accepted == 930
    assert updated.rejected == 70
    assert updated.finished_at is not None

    fetched = repo.get(load.id)
    assert fetched is not None
    assert fetched.accepted == 930
    assert fetched.finished_at is not None


def test_get_missing_returns_none(db_session: Session) -> None:
    repo = SqlAlchemyLoadRepository(db_session)
    assert repo.get(999) is None


def test_list_all_returns_all_loads(db_session: Session) -> None:
    repo = SqlAlchemyLoadRepository(db_session)
    repo.create(Load(source="historical"))
    repo.create(Load(source="api:departments"))

    assert [load.source for load in repo.list_all()] == ["historical", "api:departments"]


def test_truncate_removes_all_rows(db_session: Session) -> None:
    repo = SqlAlchemyLoadRepository(db_session)
    repo.create(Load(source="historical"))

    repo.truncate()

    assert repo.list_all() == []


def test_restore_all_preserves_id_and_resyncs_sequence(db_session: Session) -> None:
    repo = SqlAlchemyLoadRepository(db_session)
    created = repo.create(Load(source="historical"))
    assert created.id is not None
    repo.truncate()

    repo.restore_all([created])

    assert [load.id for load in repo.list_all()] == [created.id]

    # Sequence resync: a normal create() after restore must not collide with the restored id.
    next_created = repo.create(Load(source="api:departments"))
    assert next_created.id is not None
    assert next_created.id > created.id
