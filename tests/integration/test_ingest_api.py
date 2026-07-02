from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.domain.reference import Department, Job
from app.infrastructure.db.repositories import (
    SqlAlchemyDepartmentRepository,
    SqlAlchemyEmployeeRepository,
    SqlAlchemyEmployeeVersionRepository,
    SqlAlchemyJobRepository,
    SqlAlchemyRejectedRecordRepository,
)
from app.interface.api.dependencies import get_db
from app.interface.api.main import app

pytestmark = pytest.mark.usefixtures("apply_migrations")


@pytest.fixture
def client(db_session: Session) -> Iterator[TestClient]:
    def _override_get_db() -> Iterator[Session]:
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()


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


def test_ingest_departments_full_success(client: TestClient, db_session: Session) -> None:
    rows = [
        make_department_row(id=1, department="Engineering"),
        make_department_row(id=2, department="Sales"),
        make_department_row(id=3, department="Marketing"),
    ]

    response = client.post("/ingest/departments", json=rows)

    assert response.status_code == 200
    body = response.json()
    assert body["accepted"] == 3
    assert body["rejected"] == 0
    assert body["rejected_rows"] == []
    assert isinstance(body["load_id"], int)
    assert SqlAlchemyDepartmentRepository(db_session).exists(2)


def test_ingest_jobs_full_success(client: TestClient, db_session: Session) -> None:
    rows = [make_job_row(id=5, job="Recruiter"), make_job_row(id=6, job="Engineer")]

    response = client.post("/ingest/jobs", json=rows)

    assert response.status_code == 200
    body = response.json()
    assert body["accepted"] == 2
    assert body["rejected"] == 0
    assert SqlAlchemyJobRepository(db_session).exists(6)


def test_ingest_departments_wrong_typed_id_is_200_with_missing_id_reject(
    client: TestClient,
) -> None:
    rows = [make_department_row(id="not-an-int")]

    response = client.post("/ingest/departments", json=rows)

    assert response.status_code == 200
    body = response.json()
    assert body["accepted"] == 0
    assert body["rejected"] == 1
    assert body["rejected_rows"] == [
        {
            "row_index": 0,
            "field": "id",
            "reason_code": "MISSING_ID",
            "message": "id is empty or not an integer",
        }
    ]


def test_ingest_hired_employees_partial_success_exact_shape(
    client: TestClient, db_session: Session
) -> None:
    seed_department(db_session, id_=1)
    seed_job(db_session, id_=5)
    rows = [
        make_hire_row(id=1, department_id=1, job_id=5),
        make_hire_row(id=2, department_id=999, job_id=5),
        make_hire_row(id=3, department_id=1, job_id=888),
    ]

    response = client.post("/ingest/hired_employees", json=rows)

    assert response.status_code == 200
    body = response.json()
    assert body["accepted"] == 1
    assert body["rejected"] == 2
    assert len(body["rejected_rows"]) == 2
    for rejected_row in body["rejected_rows"]:
        assert set(rejected_row.keys()) == {"row_index", "field", "reason_code", "message"}
    assert {r["row_index"] for r in body["rejected_rows"]} == {1, 2}


def test_ingest_batch_over_1000_rows_returns_422(client: TestClient) -> None:
    rows = [make_department_row(id=i, department=f"D{i}") for i in range(1001)]

    response = client.post("/ingest/departments", json=rows)

    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "BATCH_TOO_LARGE"
    assert body["error"]["detail"] == {"received": 1001, "max": 1000}


def test_ingest_batch_empty_array_returns_422(client: TestClient) -> None:
    response = client.post("/ingest/departments", json=[])

    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "BATCH_TOO_LARGE"
    assert body["error"]["detail"] == {"received": 0, "min": 1}


def test_ingest_hired_employees_idempotent_reupload_is_noop(
    client: TestClient, db_session: Session
) -> None:
    seed_department(db_session, id_=1)
    seed_job(db_session, id_=5)
    row = make_hire_row(id=101, department_id=1, job_id=5)

    first = client.post("/ingest/hired_employees", json=[row])
    assert first.json()["accepted"] == 1

    second = client.post("/ingest/hired_employees", json=[row])

    assert second.status_code == 200
    body = second.json()
    assert body["accepted"] == 1
    assert body["rejected"] == 0
    versions = SqlAlchemyEmployeeVersionRepository(db_session).list_for_employee(101)
    assert len(versions) == 1


def test_ingest_hired_employees_changed_reupload_creates_new_version_and_closes_old(
    client: TestClient, db_session: Session
) -> None:
    seed_department(db_session, id_=1, name="Engineering")
    seed_department(db_session, id_=2, name="Sales")
    seed_job(db_session, id_=5)

    client.post("/ingest/hired_employees", json=[make_hire_row(id=101, department_id=1)])
    response = client.post(
        "/ingest/hired_employees", json=[make_hire_row(id=101, department_id=2)]
    )

    assert response.status_code == 200
    assert response.json()["accepted"] == 1

    versions = SqlAlchemyEmployeeVersionRepository(db_session).list_for_employee(101)
    assert len(versions) == 2
    old_version = next(v for v in versions if not v.is_current)
    new_version = next(v for v in versions if v.is_current)
    assert old_version.valid_to is not None
    assert new_version.department_id == 2
    assert new_version.valid_to is None

    # Immutable hire facts: the employees row keeps the original department.
    employee = SqlAlchemyEmployeeRepository(db_session).get(101)
    assert employee is not None
    assert employee.hire_department_id == 1


def test_ingest_hired_employees_duplicate_id_in_one_batch(
    client: TestClient, db_session: Session
) -> None:
    seed_department(db_session, id_=1, name="Engineering")
    seed_department(db_session, id_=2, name="Sales")
    seed_job(db_session, id_=5)
    rows = [
        make_hire_row(id=201, department_id=1),
        make_hire_row(id=201, department_id=2),
    ]

    response = client.post("/ingest/hired_employees", json=rows)

    assert response.status_code == 200
    body = response.json()
    assert body["accepted"] == 2
    assert body["rejected"] == 0
    versions = SqlAlchemyEmployeeVersionRepository(db_session).list_for_employee(201)
    assert len(versions) == 2
    employee = SqlAlchemyEmployeeRepository(db_session).get(201)
    assert employee is not None


def test_ingest_rejected_records_all_share_one_load_id(
    client: TestClient, db_session: Session
) -> None:
    seed_department(db_session, id_=1)
    seed_job(db_session, id_=5)
    rows = [
        make_hire_row(id=1, department_id=999),
        make_hire_row(id=2, job_id=888),
        make_hire_row(id=3, name=""),
    ]

    response = client.post("/ingest/hired_employees", json=rows)

    body = response.json()
    load_id = body["load_id"]
    records = SqlAlchemyRejectedRecordRepository(db_session).list_for_load(load_id)
    assert len(records) == 3
    assert all(r.load_id == load_id for r in records)


def test_ingest_malformed_body_returns_generic_validation_error(client: TestClient) -> None:
    response = client.post("/ingest/departments", json="not-a-list")

    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert body["error"]["detail"]["errors"]


def test_ingest_unhandled_exception_returns_500_without_stack_trace(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    def _boom(self: SqlAlchemyDepartmentRepository, department: Department) -> Department:
        raise RuntimeError("simulated infrastructure failure")

    monkeypatch.setattr(SqlAlchemyDepartmentRepository, "upsert", _boom)

    def _override_get_db() -> Iterator[Session]:
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    # raise_server_exceptions=False: assert the real ASGI response the caller would receive,
    # not TestClient's debug re-raise of the original exception.
    no_raise_client = TestClient(app, raise_server_exceptions=False)

    response = no_raise_client.post("/ingest/departments", json=[make_department_row()])
    app.dependency_overrides.clear()

    assert response.status_code == 500
    assert response.json() == {
        "error": {
            "code": "INTERNAL_ERROR",
            "message": "An unexpected error occurred",
            "detail": None,
        }
    }
    assert "RuntimeError" not in response.text
    assert "Traceback" not in response.text


def test_get_db_yields_a_working_session_that_closes_after_use() -> None:
    generator = get_db()
    session = next(generator)

    assert session.execute(text("SELECT 1")).scalar() == 1

    with pytest.raises(StopIteration):
        next(generator)


def test_get_db_rolls_back_and_closes_on_exception() -> None:
    generator = get_db()
    next(generator)

    with pytest.raises(RuntimeError):
        generator.throw(RuntimeError("boom"))
