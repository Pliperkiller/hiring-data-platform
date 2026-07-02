"""API tests for GET /reports/* (docs/API_CONTRACT.md).

The first test is the one that actually proves the Phase 3 deferral is closed: it ingests a
hire through the public endpoint and reads the report back with no manual refresh call in
between.
"""

from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

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


def test_get_hires_by_quarter_reflects_ingested_hire_without_manual_refresh(
    client: TestClient,
) -> None:
    assert client.post("/ingest/departments", json=[make_department_row()]).status_code == 200
    assert client.post("/ingest/jobs", json=[make_job_row()]).status_code == 200
    assert (
        client.post("/ingest/hired_employees", json=[make_hire_row()]).status_code == 200
    )

    response = client.get("/reports/hires-by-quarter")

    assert response.status_code == 200
    body = response.json()
    assert {
        "department": "Engineering",
        "job": "Recruiter",
        "Q1": 1,
        "Q2": 0,
        "Q3": 0,
        "Q4": 0,
    } in body


def test_get_hires_by_quarter_response_shape_matches_contract(client: TestClient) -> None:
    client.post("/ingest/departments", json=[make_department_row()])
    client.post("/ingest/jobs", json=[make_job_row()])
    client.post("/ingest/hired_employees", json=[make_hire_row()])

    response = client.get("/reports/hires-by-quarter")

    body = response.json()
    assert isinstance(body, list)
    row = body[0]
    assert set(row.keys()) == {"department", "job", "Q1", "Q2", "Q3", "Q4"}
    assert isinstance(row["department"], str)
    assert isinstance(row["job"], str)
    assert all(isinstance(row[q], int) for q in ("Q1", "Q2", "Q3", "Q4"))


def test_get_departments_above_average_reflects_load_and_matches_contract_shape(
    client: TestClient,
) -> None:
    client.post(
        "/ingest/departments",
        json=[
            make_department_row(id=1, department="Engineering"),
            {"id": 2, "department": "Sales"},
        ],
    )
    client.post(
        "/ingest/jobs", json=[make_job_row(id=5, job="Recruiter"), {"id": 6, "job": "Engineer"}]
    )
    client.post(
        "/ingest/hired_employees",
        json=[
            make_hire_row(id=101, datetime="2021-01-10T09:00:00Z"),
            make_hire_row(id=102, datetime="2021-04-10T09:00:00Z"),
            make_hire_row(id=103, datetime="2021-07-10T09:00:00Z"),
            make_hire_row(
                id=104,
                datetime="2021-01-10T09:00:00Z",
                department_id=2,
                job_id=6,
            ),
        ],
    )

    response = client.get("/reports/departments-above-average")

    assert response.status_code == 200
    body = response.json()
    assert body == [{"id": 1, "department": "Engineering", "hired": 3}]
    row = body[0]
    assert set(row.keys()) == {"id", "department", "hired"}
    assert isinstance(row["id"], int)
    assert isinstance(row["department"], str)
    assert isinstance(row["hired"], int)
