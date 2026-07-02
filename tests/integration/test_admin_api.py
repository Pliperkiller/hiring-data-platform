"""API tests for POST /admin/backup/{table}, POST /admin/restore/{table}, and POST /admin/reset
(docs/API_CONTRACT.md).
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

import app.application.backup as backup_module
import app.application.restore as restore_module
from app.domain.employee import Employee
from app.domain.reference import Department, Job
from app.infrastructure.db.repositories import (
    SqlAlchemyDepartmentRepository,
    SqlAlchemyEmployeeRepository,
    SqlAlchemyJobRepository,
    SqlAlchemyReportRepository,
)
from app.interface.api.dependencies import get_db
from app.interface.api.main import app

pytestmark = pytest.mark.usefixtures("apply_migrations")


@pytest.fixture
def client(
    db_session: Session, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Iterator[TestClient]:
    def _override_get_db() -> Iterator[Session]:
        yield db_session

    monkeypatch.setattr(backup_module, "DEFAULT_DATA_DIR", tmp_path)
    monkeypatch.setattr(restore_module, "DEFAULT_DATA_DIR", tmp_path)
    app.dependency_overrides[get_db] = _override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_backup_then_restore_round_trip(client: TestClient, db_session: Session) -> None:
    SqlAlchemyDepartmentRepository(db_session).upsert(Department(id=1, name="Engineering"))

    backup_response = client.post("/admin/backup/departments")
    assert backup_response.status_code == 200
    assert backup_response.json()["table"] == "departments"

    restore_response = client.post("/admin/restore/departments")
    assert restore_response.status_code == 200
    assert restore_response.json() == {"table": "departments", "restored": 1}
    assert SqlAlchemyDepartmentRepository(db_session).list_all() == [
        Department(id=1, name="Engineering")
    ]


def test_download_backup_returns_the_avro_file(client: TestClient, db_session: Session) -> None:
    SqlAlchemyDepartmentRepository(db_session).upsert(Department(id=1, name="Engineering"))
    client.post("/admin/backup/departments")

    response = client.get("/admin/backup/departments")

    assert response.status_code == 200
    assert response.content == (backup_module.DEFAULT_DATA_DIR / "departments.avro").read_bytes()
    assert response.headers["content-disposition"] == 'attachment; filename="departments.avro"'


def test_download_backup_unknown_table_returns_404(client: TestClient) -> None:
    response = client.get("/admin/backup/bogus")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "UNKNOWN_TABLE"


def test_download_backup_missing_file_returns_404(client: TestClient) -> None:
    response = client.get("/admin/backup/departments")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "BACKUP_NOT_FOUND"


def test_backup_unknown_table_returns_404(client: TestClient) -> None:
    response = client.post("/admin/backup/bogus")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "UNKNOWN_TABLE"


def test_restore_unknown_table_returns_404(client: TestClient) -> None:
    response = client.post("/admin/restore/bogus")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "UNKNOWN_TABLE"


def test_restore_missing_backup_file_returns_404(client: TestClient) -> None:
    response = client.post("/admin/restore/departments")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "BACKUP_NOT_FOUND"


def test_reset_empties_all_tables_and_refreshes_report_views(
    client: TestClient, db_session: Session
) -> None:
    SqlAlchemyDepartmentRepository(db_session).upsert(Department(id=1, name="Engineering"))
    SqlAlchemyJobRepository(db_session).upsert(Job(id=5, name="Recruiter"))
    SqlAlchemyEmployeeRepository(db_session).add(
        Employee(
            employee_id=101,
            name_at_hire="Ada Lovelace",
            hire_datetime=datetime(2021, 2, 10, 9, 30, tzinfo=UTC),
            hire_department_id=1,
            hire_job_id=5,
        )
    )
    db_session.commit()
    report_repo = SqlAlchemyReportRepository(db_session)
    report_repo.refresh_views()

    response = client.post("/admin/reset")

    assert response.status_code == 200
    assert response.json() == {"reset": True}
    assert SqlAlchemyDepartmentRepository(db_session).list_all() == []
    assert SqlAlchemyJobRepository(db_session).list_all() == []
    assert SqlAlchemyEmployeeRepository(db_session).list_all() == []
    assert report_repo.list_hires_by_quarter() == []
    assert report_repo.list_departments_above_average() == []
