import pytest
from sqlalchemy.orm import Session

from app.domain.reference import Job
from app.infrastructure.db.repositories import SqlAlchemyJobRepository

pytestmark = pytest.mark.usefixtures("apply_migrations")


def test_upsert_inserts_new(db_session: Session) -> None:
    repo = SqlAlchemyJobRepository(db_session)

    result = repo.upsert(Job(id=1, name="Recruiter"))

    assert result == Job(id=1, name="Recruiter")
    assert repo.get(1) == Job(id=1, name="Recruiter")


def test_upsert_updates_existing_name(db_session: Session) -> None:
    repo = SqlAlchemyJobRepository(db_session)
    repo.upsert(Job(id=1, name="Recruiter"))

    repo.upsert(Job(id=1, name="Senior Recruiter"))

    assert repo.get(1) == Job(id=1, name="Senior Recruiter")
    assert len(repo.list_all()) == 1


def test_get_missing_returns_none(db_session: Session) -> None:
    repo = SqlAlchemyJobRepository(db_session)
    assert repo.get(999) is None


def test_list_all_ordered_by_id(db_session: Session) -> None:
    repo = SqlAlchemyJobRepository(db_session)
    repo.upsert(Job(id=2, name="Engineer"))
    repo.upsert(Job(id=1, name="Recruiter"))

    assert [j.id for j in repo.list_all()] == [1, 2]


def test_exists(db_session: Session) -> None:
    repo = SqlAlchemyJobRepository(db_session)
    repo.upsert(Job(id=1, name="Recruiter"))

    assert repo.exists(1) is True
    assert repo.exists(2) is False


def test_truncate_removes_all_rows(db_session: Session) -> None:
    repo = SqlAlchemyJobRepository(db_session)
    repo.upsert(Job(id=1, name="Recruiter"))
    repo.upsert(Job(id=2, name="Engineer"))

    repo.truncate()

    assert repo.list_all() == []
