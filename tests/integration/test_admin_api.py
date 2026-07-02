"""API tests for POST /admin/backup/{table} and POST /admin/restore/{table}
(docs/API_CONTRACT.md).
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

import app.application.backup as backup_module
import app.application.restore as restore_module
from app.domain.reference import Department
from app.infrastructure.db.repositories import SqlAlchemyDepartmentRepository
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
