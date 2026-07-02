from datetime import UTC, datetime

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.domain.employee import Employee
from app.domain.reference import Department, Job
from app.infrastructure.db.repositories import (
    SqlAlchemyDepartmentRepository,
    SqlAlchemyEmployeeRepository,
    SqlAlchemyJobRepository,
)

pytestmark = pytest.mark.usefixtures("apply_migrations")


def seed_department_and_job(session: Session) -> None:
    SqlAlchemyDepartmentRepository(session).upsert(Department(id=1, name="Engineering"))
    SqlAlchemyJobRepository(session).upsert(Job(id=1, name="Recruiter"))


def make_employee(**overrides: object) -> Employee:
    defaults: dict[str, object] = {
        "employee_id": 1,
        "name_at_hire": "Alice",
        "hire_datetime": datetime(2021, 3, 15, tzinfo=UTC),
        "hire_department_id": 1,
        "hire_job_id": 1,
    }
    defaults.update(overrides)
    return Employee(**defaults)  # type: ignore[arg-type]


def test_add_persists_and_populates_first_loaded_at(db_session: Session) -> None:
    seed_department_and_job(db_session)
    repo = SqlAlchemyEmployeeRepository(db_session)

    result = repo.add(make_employee())

    assert result.first_loaded_at is not None
    assert result.first_loaded_at.tzinfo is not None


def test_add_with_unknown_department_raises_integrity_error(db_session: Session) -> None:
    SqlAlchemyJobRepository(db_session).upsert(Job(id=1, name="Recruiter"))
    repo = SqlAlchemyEmployeeRepository(db_session)

    with pytest.raises(IntegrityError):
        repo.add(make_employee(hire_department_id=999))


def test_get_and_exists(db_session: Session) -> None:
    seed_department_and_job(db_session)
    repo = SqlAlchemyEmployeeRepository(db_session)
    repo.add(make_employee())

    assert repo.get(1) == repo.get(1)
    assert repo.exists(1) is True
    assert repo.exists(999) is False
    assert repo.get(999) is None


def test_list_all(db_session: Session) -> None:
    seed_department_and_job(db_session)
    repo = SqlAlchemyEmployeeRepository(db_session)
    repo.add(make_employee(employee_id=2))
    repo.add(make_employee(employee_id=1))

    assert [e.employee_id for e in repo.list_all()] == [1, 2]


def test_readding_same_employee_id_raises_integrity_error(db_session: Session) -> None:
    seed_department_and_job(db_session)
    repo = SqlAlchemyEmployeeRepository(db_session)
    repo.add(make_employee())

    with pytest.raises(IntegrityError):
        repo.add(make_employee(name_at_hire="Alice Again"))
