"""Unit tests for the Backup use case's dispatch logic, against fake repositories (no DB)."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.application.backup import Backup, main
from app.domain.employee import Employee, EmployeeVersion
from app.domain.reference import Department, Job
from app.domain.rejected_record import Load, RejectedRecord
from app.domain.value_objects import ReasonCode
from app.infrastructure.avro.codec import read_avro
from tests.unit.fakes import (
    FakeDepartmentRepository,
    FakeEmployeeRepository,
    FakeEmployeeVersionRepository,
    FakeJobRepository,
    FakeLoadRepository,
    FakeRejectedRecordRepository,
)

UTC_NOW = datetime(2021, 3, 15, 9, 30, tzinfo=UTC)


def make_backup(tmp_path: Path) -> Backup:
    return Backup(
        department_repo=FakeDepartmentRepository({1: Department(id=1, name="Engineering")}),
        job_repo=FakeJobRepository({5: Job(id=5, name="Recruiter")}),
        employee_repo=FakeEmployeeRepository(
            {
                101: Employee(
                    employee_id=101,
                    name_at_hire="Ada",
                    hire_datetime=UTC_NOW,
                    hire_department_id=1,
                    hire_job_id=5,
                    first_loaded_at=UTC_NOW,
                )
            }
        ),
        employee_version_repo=FakeEmployeeVersionRepository(
            [
                EmployeeVersion(
                    version_id=1,
                    employee_id=101,
                    name="Ada",
                    department_id=1,
                    job_id=5,
                    valid_from=UTC_NOW,
                    valid_to=None,
                    is_current=True,
                )
            ]
        ),
        load_repo=FakeLoadRepository(
            [Load(id=1, source="api:departments", started_at=UTC_NOW, finished_at=UTC_NOW)]
        ),
        rejected_record_repo=FakeRejectedRecordRepository(
            [
                RejectedRecord(
                    id=1,
                    target_table="departments",
                    raw_payload={"id": "x"},
                    reason_code=ReasonCode.MISSING_ID,
                    message="id is empty",
                    field="id",
                    load_id=1,
                    created_at=UTC_NOW,
                )
            ]
        ),
        data_dir=tmp_path,
    )


@pytest.mark.parametrize(
    "table",
    [
        "departments",
        "jobs",
        "employees",
        "employee_versions",
        "loads",
        "rejected_records",
    ],
)
def test_backup_run_writes_avro_file_for_requested_table(tmp_path: Path, table: str) -> None:
    backup = make_backup(tmp_path)

    path = backup.run(table)

    assert path == tmp_path / f"{table}.avro"
    assert path.exists()
    assert len(read_avro(path)) == 1


def test_backup_run_rejects_unknown_table(tmp_path: Path) -> None:
    backup = make_backup(tmp_path)

    with pytest.raises(ValueError):
        backup.run("bogus")

    assert list(tmp_path.iterdir()) == []


def test_main_rejects_bad_argv_count_without_touching_the_db(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _fail_if_called(*args: object, **kwargs: object) -> None:
        raise AssertionError("build_engine must not be called for invalid argv")

    monkeypatch.setattr("app.infrastructure.db.session.build_engine", _fail_if_called)

    assert main(["backup.py"]) == 2
    assert main(["backup.py", "departments", "extra"]) == 2


def test_main_rejects_unknown_table_without_touching_the_db(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _fail_if_called(*args: object, **kwargs: object) -> None:
        raise AssertionError("build_engine must not be called for an unknown table")

    monkeypatch.setattr("app.infrastructure.db.session.build_engine", _fail_if_called)

    assert main(["backup.py", "bogus"]) == 2
