import pytest
from sqlalchemy.orm import Session

from app.domain.reference import Department
from app.infrastructure.db.repositories import SqlAlchemyDepartmentRepository

pytestmark = pytest.mark.usefixtures("apply_migrations")


def test_upsert_inserts_new(db_session: Session) -> None:
    repo = SqlAlchemyDepartmentRepository(db_session)

    result = repo.upsert(Department(id=1, name="Engineering"))

    assert result == Department(id=1, name="Engineering")
    assert repo.get(1) == Department(id=1, name="Engineering")


def test_upsert_updates_existing_name(db_session: Session) -> None:
    repo = SqlAlchemyDepartmentRepository(db_session)
    repo.upsert(Department(id=1, name="Engineering"))

    repo.upsert(Department(id=1, name="Engineering & Product"))

    assert repo.get(1) == Department(id=1, name="Engineering & Product")
    assert len(repo.list_all()) == 1


def test_get_missing_returns_none(db_session: Session) -> None:
    repo = SqlAlchemyDepartmentRepository(db_session)
    assert repo.get(999) is None


def test_list_all_ordered_by_id(db_session: Session) -> None:
    repo = SqlAlchemyDepartmentRepository(db_session)
    repo.upsert(Department(id=2, name="Sales"))
    repo.upsert(Department(id=1, name="Engineering"))

    assert [d.id for d in repo.list_all()] == [1, 2]


def test_exists(db_session: Session) -> None:
    repo = SqlAlchemyDepartmentRepository(db_session)
    repo.upsert(Department(id=1, name="Engineering"))

    assert repo.exists(1) is True
    assert repo.exists(2) is False
