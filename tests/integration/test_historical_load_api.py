"""Integration test(s) for the historical-load orchestration against the real /ingest/*
API, following the same TestClient + db_session pattern as test_ingest_api.py. Uses small
synthetic multi-batch data (never the real ./files/ CSVs, which don't exist in CI)."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.domain.reference import Department, Job
from app.infrastructure.db.repositories import (
    SqlAlchemyDepartmentRepository,
    SqlAlchemyEmployeeRepository,
    SqlAlchemyJobRepository,
)
from app.interface.api.dependencies import get_db
from app.interface.api.main import app
from app.interface.ui.historical_load import PostResult, TableName, run_historical_load

pytestmark = pytest.mark.usefixtures("apply_migrations")

_ENDPOINT_BY_TABLE: dict[TableName, str] = {
    "departments": "/ingest/departments",
    "jobs": "/ingest/jobs",
    "hired_employees": "/ingest/hired_employees",
}


@pytest.fixture
def client(db_session: Session) -> Iterator[TestClient]:
    def _override_get_db() -> Iterator[Session]:
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()


def _post_fn_from_client(test_client: TestClient) -> Any:
    def post_fn(table: TableName, batch: list[dict[str, Any]]) -> PostResult:
        response = test_client.post(_ENDPOINT_BY_TABLE[table], json=batch)
        return PostResult(status_code=response.status_code, body=response.json())

    return post_fn


def seed_department(session: Session, id_: int = 1, name: str = "Engineering") -> None:
    SqlAlchemyDepartmentRepository(session).upsert(Department(id=id_, name=name))


def seed_job(session: Session, id_: int = 5, name: str = "Recruiter") -> None:
    SqlAlchemyJobRepository(session).upsert(Job(id=id_, name=name))


def make_department_row(**overrides: Any) -> dict[str, Any]:
    row: dict[str, Any] = {"id": 1, "department": "Engineering"}
    row.update(overrides)
    return row


def make_job_row(**overrides: Any) -> dict[str, Any]:
    row: dict[str, Any] = {"id": 5, "job": "Recruiter"}
    row.update(overrides)
    return row


def make_hire_row(**overrides: Any) -> dict[str, Any]:
    row: dict[str, Any] = {
        "id": 101,
        "name": "Ada Lovelace",
        "datetime": "2021-02-10T09:30:00Z",
        "department_id": 1,
        "job_id": 5,
    }
    row.update(overrides)
    return row


def test_historical_load_end_to_end_small_batches(client: TestClient, db_session: Session) -> None:
    rows = [make_department_row(id=i, department=f"Dept {i}") for i in range(1, 6)]

    summary = run_historical_load(
        {"departments": rows}, _post_fn_from_client(client), batch_size=2
    )

    assert [o.row_count for o in summary.batch_outcomes] == [2, 2, 1]
    assert summary.total_accepted == 5
    assert summary.total_rejected == 0
    repo = SqlAlchemyDepartmentRepository(db_session)
    assert all(repo.exists(i) for i in range(1, 6))


def test_historical_load_dependency_order_against_real_db(
    client: TestClient, db_session: Session
) -> None:
    files: dict[TableName, list[dict[str, Any]]] = {
        "departments": [make_department_row(id=1, department="Engineering")],
        "jobs": [make_job_row(id=5, job="Recruiter")],
        "hired_employees": [make_hire_row(id=101, department_id=1, job_id=5)],
    }

    summary = run_historical_load(files, _post_fn_from_client(client), batch_size=2)

    assert summary.total_accepted == 3
    assert summary.total_rejected == 0
    employee = SqlAlchemyEmployeeRepository(db_session).get(101)
    assert employee is not None
    assert employee.hire_department_id == 1
    assert employee.hire_job_id == 5


def test_historical_load_partial_rejection_across_batches_is_disambiguated(
    client: TestClient, db_session: Session
) -> None:
    seed_department(db_session, id_=1)
    seed_job(db_session, id_=5)
    rows = [
        make_hire_row(id=1),
        make_hire_row(id=2, name=""),
        make_hire_row(id=3),
        make_hire_row(id=4, name=""),
    ]

    summary = run_historical_load(
        {"hired_employees": rows}, _post_fn_from_client(client), batch_size=2
    )

    assert summary.total_accepted == 2
    assert summary.total_rejected == 2
    assert len(summary.rejected_rows) == 2
    first, second = summary.rejected_rows
    assert first.table == second.table == "hired_employees"
    assert first.row_index == second.row_index == 1
    assert first.batch_index != second.batch_index
    assert {first.batch_index, second.batch_index} == {0, 1}
    assert first.reason_code == second.reason_code == "MISSING_NAME"


def test_historical_load_continues_after_one_batch_http_error(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    original_upsert = SqlAlchemyDepartmentRepository.upsert
    call_count = {"n": 0}

    def _flaky_upsert(self: SqlAlchemyDepartmentRepository, department: Department) -> Department:
        call_count["n"] += 1
        if call_count["n"] == 3:
            raise RuntimeError("simulated infrastructure failure")
        return original_upsert(self, department)

    monkeypatch.setattr(SqlAlchemyDepartmentRepository, "upsert", _flaky_upsert)

    def _override_get_db() -> Iterator[Session]:
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    no_raise_client = TestClient(app, raise_server_exceptions=False)

    rows = [make_department_row(id=i, department=f"Dept {i}") for i in range(1, 5)]
    summary = run_historical_load(
        {"departments": rows}, _post_fn_from_client(no_raise_client), batch_size=2
    )

    app.dependency_overrides.clear()

    assert len(summary.batch_outcomes) == 2
    assert len(summary.failed_batches) == 1
    assert summary.failed_batches[0].batch_index == 1
    successful = [o for o in summary.batch_outcomes if o.success]
    assert len(successful) == 1
    assert successful[0].accepted == 2


def test_historical_load_reference_table_failure_flag(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    original_upsert = SqlAlchemyDepartmentRepository.upsert

    def _always_boom(self: SqlAlchemyDepartmentRepository, department: Department) -> Department:
        raise RuntimeError("simulated infrastructure failure")

    def _override_get_db() -> Iterator[Session]:
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    no_raise_client = TestClient(app, raise_server_exceptions=False)
    post_fn = _post_fn_from_client(no_raise_client)

    monkeypatch.setattr(SqlAlchemyDepartmentRepository, "upsert", _always_boom)
    failing_summary = run_historical_load(
        {"departments": [make_department_row(id=101, department="Failing")]}, post_fn
    )
    assert failing_summary.reference_table_failed is True

    monkeypatch.setattr(SqlAlchemyDepartmentRepository, "upsert", original_upsert)
    ok_summary = run_historical_load(
        {"departments": [make_department_row(id=102, department="OK")]}, post_fn
    )
    assert ok_summary.reference_table_failed is False

    app.dependency_overrides.clear()
