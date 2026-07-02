from datetime import UTC, datetime

import pytest
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

pytestmark = pytest.mark.usefixtures("apply_migrations")


def test_upgrade_head_creates_all_tables(engine) -> None:  # type: ignore[no-untyped-def]
    tables = set(inspect(engine).get_table_names())
    expected = {
        "departments",
        "jobs",
        "employees",
        "employee_versions",
        "loads",
        "rejected_records",
    }
    assert expected.issubset(tables)


def test_upgrade_head_creates_report_materialized_views(engine) -> None:  # type: ignore[no-untyped-def]
    views = set(inspect(engine).get_materialized_view_names())
    assert {"report_hires_by_quarter", "report_departments_above_average"}.issubset(views)


def test_report_materialized_views_refresh_after_data_loaded(db_session: Session) -> None:
    db_session.execute(text("INSERT INTO departments (id, department) VALUES (1, 'Eng')"))
    db_session.execute(text("INSERT INTO jobs (id, job) VALUES (1, 'Recruiter')"))
    db_session.execute(
        text(
            "INSERT INTO employees "
            "(employee_id, name_at_hire, hire_datetime, hire_department_id, hire_job_id) "
            "VALUES (1, 'Alice', :hire_datetime, 1, 1)"
        ),
        {"hire_datetime": datetime(2021, 3, 15, tzinfo=UTC)},
    )
    db_session.flush()

    db_session.execute(text("REFRESH MATERIALIZED VIEW report_hires_by_quarter"))
    db_session.execute(text("REFRESH MATERIALIZED VIEW report_departments_above_average"))

    hires_row = db_session.execute(
        text("SELECT department, job, \"Q1\" FROM report_hires_by_quarter")
    ).one()
    assert hires_row == ("Eng", "Recruiter", 1)


def test_employee_versions_partial_unique_index_enforced(db_session: Session) -> None:
    db_session.execute(text("INSERT INTO departments (id, department) VALUES (1, 'Eng')"))
    db_session.execute(text("INSERT INTO jobs (id, job) VALUES (1, 'Recruiter')"))
    db_session.execute(
        text(
            "INSERT INTO employees "
            "(employee_id, name_at_hire, hire_datetime, hire_department_id, hire_job_id) "
            "VALUES (1, 'Alice', :hire_datetime, 1, 1)"
        ),
        {"hire_datetime": datetime(2021, 3, 15, tzinfo=UTC)},
    )
    db_session.execute(
        text(
            "INSERT INTO employee_versions "
            "(employee_id, name, department_id, job_id, valid_from, is_current) "
            "VALUES (1, 'Alice', 1, 1, :valid_from, true)"
        ),
        {"valid_from": datetime(2021, 3, 15, tzinfo=UTC)},
    )

    # A second is_current=True row for the same employee violates the partial unique
    # index. Isolate the attempt in a SAVEPOINT so the earlier inserts survive the
    # failure (Postgres aborts the whole transaction on IntegrityError otherwise).
    with pytest.raises(IntegrityError), db_session.begin_nested():
        db_session.execute(
            text(
                "INSERT INTO employee_versions "
                "(employee_id, name, department_id, job_id, valid_from, is_current) "
                "VALUES (1, 'Alice B', 1, 1, :valid_from, true)"
            ),
            {"valid_from": datetime(2021, 6, 1, tzinfo=UTC)},
        )

    # A second, non-current version for the same employee is fine (index is partial).
    db_session.execute(
        text(
            "INSERT INTO employee_versions "
            "(employee_id, name, department_id, job_id, valid_from, valid_to, is_current) "
            "VALUES (1, 'Alice B', 1, 1, :valid_from, :valid_to, false)"
        ),
        {
            "valid_from": datetime(2021, 3, 15, tzinfo=UTC),
            "valid_to": datetime(2021, 6, 1, tzinfo=UTC),
        },
    )
    db_session.flush()
