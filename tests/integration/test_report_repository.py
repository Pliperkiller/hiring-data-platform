"""Proves the report SQL logic itself: year filter, quarter bucketing, and the
above-average-over-hiring-departments threshold — not just that the queries run.
"""

from datetime import UTC, datetime

import pytest
from sqlalchemy.orm import Session

from app.domain.employee import Employee
from app.domain.reference import Department, Job
from app.infrastructure.db.repositories import (
    SqlAlchemyDepartmentRepository,
    SqlAlchemyEmployeeRepository,
    SqlAlchemyJobRepository,
    SqlAlchemyReportRepository,
)

pytestmark = pytest.mark.usefixtures("apply_migrations")


def make_employee(employee_id: int, **overrides: object) -> Employee:
    defaults: dict[str, object] = {
        "employee_id": employee_id,
        "name_at_hire": f"Employee {employee_id}",
        "hire_datetime": datetime(2021, 1, 1, tzinfo=UTC),
        "hire_department_id": 1,
        "hire_job_id": 1,
    }
    defaults.update(overrides)
    return Employee(**defaults)  # type: ignore[arg-type]


def seed(session: Session) -> None:
    dept_repo = SqlAlchemyDepartmentRepository(session)
    job_repo = SqlAlchemyJobRepository(session)
    dept_repo.upsert(Department(id=1, name="Engineering"))
    dept_repo.upsert(Department(id=2, name="Sales"))
    dept_repo.upsert(Department(id=3, name="Marketing"))
    job_repo.upsert(Job(id=1, name="Engineer"))
    job_repo.upsert(Job(id=2, name="Recruiter"))

    employee_repo = SqlAlchemyEmployeeRepository(session)
    # Engineering / Engineer: 2 hires in Q1, 1 in Q2 -> 3 hires in 2021.
    employee_repo.add(
        make_employee(1, hire_datetime=datetime(2021, 1, 10, tzinfo=UTC))
    )
    employee_repo.add(
        make_employee(2, hire_datetime=datetime(2021, 2, 15, tzinfo=UTC))
    )
    employee_repo.add(
        make_employee(3, hire_datetime=datetime(2021, 4, 1, tzinfo=UTC))
    )
    # Sales / Recruiter: 1 hire in Q3, 1 in Q4 -> 2 hires in 2021.
    employee_repo.add(
        make_employee(
            4,
            hire_datetime=datetime(2021, 7, 1, tzinfo=UTC),
            hire_department_id=2,
            hire_job_id=2,
        )
    )
    employee_repo.add(
        make_employee(
            5,
            hire_datetime=datetime(2021, 10, 1, tzinfo=UTC),
            hire_department_id=2,
            hire_job_id=2,
        )
    )
    # Marketing / Engineer: 1 hire in Q1 -> 1 hire in 2021.
    employee_repo.add(
        make_employee(
            6, hire_datetime=datetime(2021, 1, 20, tzinfo=UTC), hire_department_id=3
        )
    )
    # 2022 hire for Engineering: must be excluded from both reports (year filter).
    employee_repo.add(
        make_employee(7, hire_datetime=datetime(2022, 5, 1, tzinfo=UTC))
    )
    session.commit()


def test_list_hires_by_quarter_applies_year_filter_and_quarter_bucketing(
    db_session: Session,
) -> None:
    seed(db_session)
    repo = SqlAlchemyReportRepository(db_session)
    repo.refresh_views()

    rows = repo.list_hires_by_quarter()

    assert [(r.department, r.job) for r in rows] == [
        ("Engineering", "Engineer"),
        ("Marketing", "Engineer"),
        ("Sales", "Recruiter"),
    ]
    engineering = next(r for r in rows if r.department == "Engineering")
    assert (engineering.q1, engineering.q2, engineering.q3, engineering.q4) == (2, 1, 0, 0)
    sales = next(r for r in rows if r.department == "Sales")
    assert (sales.q1, sales.q2, sales.q3, sales.q4) == (0, 0, 1, 1)
    marketing = next(r for r in rows if r.department == "Marketing")
    assert (marketing.q1, marketing.q2, marketing.q3, marketing.q4) == (1, 0, 0, 0)


def test_list_departments_above_average_uses_average_over_hiring_departments(
    db_session: Session,
) -> None:
    seed(db_session)
    repo = SqlAlchemyReportRepository(db_session)
    repo.refresh_views()

    rows = repo.list_departments_above_average()

    # Hiring departments: Engineering=3, Sales=2, Marketing=1 -> average 2.0.
    # The 2022 Engineering hire must not inflate the count to 4 or shift the average.
    assert [(r.id, r.department, r.hired) for r in rows] == [(1, "Engineering", 3)]
