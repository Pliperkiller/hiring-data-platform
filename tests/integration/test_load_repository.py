from datetime import UTC, datetime, timedelta

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


def test_recent_stats_only_counts_finished_loads_in_window(db_session: Session) -> None:
    repo = SqlAlchemyLoadRepository(db_session)
    since = datetime.now(UTC) - timedelta(minutes=1)

    first = repo.create(Load(source="api:departments"))
    assert first.id is not None
    repo.mark_finished(first.id, accepted=8, rejected=2)

    second = repo.create(Load(source="api:jobs"))
    assert second.id is not None
    repo.mark_finished(second.id, accepted=5, rejected=5)

    # In-flight load: no finished_at yet, must not be counted.
    repo.create(Load(source="api:hired_employees"))

    stats = repo.recent_stats(since)

    assert stats.total_loads == 2
    assert stats.total_accepted == 13
    assert stats.total_rejected == 7
    assert stats.average_reject_rate == pytest.approx(7 / 20)


def test_recent_stats_excludes_loads_before_since(db_session: Session) -> None:
    repo = SqlAlchemyLoadRepository(db_session)
    old = repo.create(Load(source="api:departments"))
    assert old.id is not None
    repo.mark_finished(old.id, accepted=1, rejected=1)

    cutoff = datetime.now(UTC) + timedelta(minutes=1)

    stats = repo.recent_stats(cutoff)

    assert stats.total_loads == 0
    assert stats.total_accepted == 0
    assert stats.total_rejected == 0
    assert stats.average_reject_rate == 0.0


def test_recent_stats_empty_window_returns_zero_rate(db_session: Session) -> None:
    repo = SqlAlchemyLoadRepository(db_session)

    stats = repo.recent_stats(datetime.now(UTC) - timedelta(days=7))

    assert stats.total_loads == 0
    assert stats.average_reject_rate == 0.0
