from datetime import UTC, datetime

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.domain.employee import Employee, EmployeeVersion
from app.domain.reference import Department, Job
from app.infrastructure.db.repositories import (
    SqlAlchemyDepartmentRepository,
    SqlAlchemyEmployeeRepository,
    SqlAlchemyEmployeeVersionRepository,
    SqlAlchemyJobRepository,
)

pytestmark = pytest.mark.usefixtures("apply_migrations")


def seed_employee(session: Session, employee_id: int = 1) -> None:
    SqlAlchemyDepartmentRepository(session).upsert(Department(id=1, name="Engineering"))
    SqlAlchemyJobRepository(session).upsert(Job(id=1, name="Recruiter"))
    SqlAlchemyEmployeeRepository(session).add(
        Employee(
            employee_id=employee_id,
            name_at_hire="Alice",
            hire_datetime=datetime(2021, 3, 15, tzinfo=UTC),
            hire_department_id=1,
            hire_job_id=1,
            name="Alice",
            department_id=1,
            job_id=1,
        )
    )


def make_version(**overrides: object) -> EmployeeVersion:
    defaults: dict[str, object] = {
        "employee_id": 1,
        "name": "Alice",
        "department_id": 1,
        "job_id": 1,
        "valid_from": datetime(2021, 3, 15, tzinfo=UTC),
        "valid_to": None,
        "is_current": True,
    }
    defaults.update(overrides)
    return EmployeeVersion(**defaults)  # type: ignore[arg-type]


def test_add_creates_open_version_and_get_current_retrieves_it(db_session: Session) -> None:
    seed_employee(db_session)
    repo = SqlAlchemyEmployeeVersionRepository(db_session)

    added = repo.add(make_version())

    assert added.version_id is not None
    current = repo.get_current(1)
    assert current is not None
    assert current.is_current is True
    assert current.valid_to is None


def test_close_current_then_reopen(db_session: Session) -> None:
    seed_employee(db_session)
    repo = SqlAlchemyEmployeeVersionRepository(db_session)
    repo.add(make_version())

    repo.close_current(1, datetime(2021, 6, 1, tzinfo=UTC))
    assert repo.get_current(1) is None

    repo.add(make_version(name="Alice B", valid_from=datetime(2021, 6, 1, tzinfo=UTC)))

    current = repo.get_current(1)
    assert current is not None
    assert current.name == "Alice B"


def test_list_for_employee_returns_all_versions_ordered(db_session: Session) -> None:
    seed_employee(db_session)
    repo = SqlAlchemyEmployeeVersionRepository(db_session)
    repo.add(make_version())
    repo.close_current(1, datetime(2021, 6, 1, tzinfo=UTC))
    repo.add(make_version(name="Alice B", valid_from=datetime(2021, 6, 1, tzinfo=UTC)))

    versions = repo.list_for_employee(1)

    assert [v.name for v in versions] == ["Alice", "Alice B"]


def test_second_open_version_without_closing_raises_integrity_error(
    db_session: Session,
) -> None:
    seed_employee(db_session)
    repo = SqlAlchemyEmployeeVersionRepository(db_session)
    repo.add(make_version())

    with pytest.raises(IntegrityError):
        repo.add(make_version(name="Alice B", valid_from=datetime(2021, 6, 1, tzinfo=UTC)))


def test_list_all_returns_all_versions(db_session: Session) -> None:
    seed_employee(db_session)
    repo = SqlAlchemyEmployeeVersionRepository(db_session)
    repo.add(make_version())
    repo.close_current(1, datetime(2021, 6, 1, tzinfo=UTC))
    repo.add(make_version(name="Alice B", valid_from=datetime(2021, 6, 1, tzinfo=UTC)))

    assert [v.name for v in repo.list_all()] == ["Alice", "Alice B"]


def test_truncate_removes_all_rows(db_session: Session) -> None:
    seed_employee(db_session)
    repo = SqlAlchemyEmployeeVersionRepository(db_session)
    repo.add(make_version())

    repo.truncate()

    assert repo.list_all() == []


def test_restore_all_preserves_version_id_and_resyncs_sequence(db_session: Session) -> None:
    seed_employee(db_session)
    repo = SqlAlchemyEmployeeVersionRepository(db_session)
    added = repo.add(make_version())
    assert added.version_id is not None
    repo.truncate()

    repo.restore_all([added])

    assert [v.version_id for v in repo.list_all()] == [added.version_id]

    # Sequence resync: a normal add() after restore must not collide with the restored id.
    # Close the restored (is_current=True) row first — the partial unique index only allows
    # one current row per employee, and this check is only about the id sequence, not SCD.
    repo.close_current(1, datetime(2021, 6, 1, tzinfo=UTC))
    next_added = repo.add(
        make_version(name="Alice B", valid_from=datetime(2021, 6, 1, tzinfo=UTC))
    )
    assert next_added.version_id is not None
    assert next_added.version_id > added.version_id
