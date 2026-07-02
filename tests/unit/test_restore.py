"""Unit tests for the Restore use case's dispatch logic, against fake repositories (no DB)."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.application.restore import Restore
from app.domain.reference import Department
from app.infrastructure.avro.avro_backup_codec import AvroBackupCodec
from app.infrastructure.avro.codec import write_avro
from tests.unit.fakes import (
    FakeDepartmentRepository,
    FakeEmployeeRepository,
    FakeEmployeeVersionRepository,
    FakeJobRepository,
    FakeLoadRepository,
    FakeRejectedRecordRepository,
    FakeSession,
)

UTC_NOW = datetime(2021, 3, 15, 9, 30, tzinfo=UTC)


def make_restore(tmp_path: Path) -> tuple[Restore, FakeDepartmentRepository, FakeSession]:
    department_repo = FakeDepartmentRepository()
    session = FakeSession()
    restore = Restore(
        department_repo=department_repo,
        job_repo=FakeJobRepository(),
        employee_repo=FakeEmployeeRepository(),
        employee_version_repo=FakeEmployeeVersionRepository(),
        load_repo=FakeLoadRepository(),
        rejected_record_repo=FakeRejectedRecordRepository(),
        session=session,  # type: ignore[arg-type]
        codec=AvroBackupCodec(),
        data_dir=tmp_path,
    )
    return restore, department_repo, session


def test_restore_run_truncates_then_inserts(tmp_path: Path) -> None:
    write_avro(
        "departments",
        [{"id": 1, "name": "Engineering"}],
        tmp_path / "departments.avro",
    )
    restore, department_repo, session = make_restore(tmp_path)

    count = restore.run("departments")

    assert count == 1
    assert department_repo.truncate_called is True
    assert department_repo.get(1) == Department(id=1, name="Engineering")
    assert session.commit_count == 1


def test_restore_run_rejects_unknown_table(tmp_path: Path) -> None:
    restore, _, _ = make_restore(tmp_path)

    with pytest.raises(ValueError):
        restore.run("bogus")


def test_restore_run_missing_backup_file_raises(tmp_path: Path) -> None:
    restore, _, _ = make_restore(tmp_path)

    with pytest.raises(FileNotFoundError):
        restore.run("departments")


def test_restore_run_returns_row_count(tmp_path: Path) -> None:
    write_avro(
        "departments",
        [{"id": 1, "name": "Engineering"}, {"id": 2, "name": "Sales"}],
        tmp_path / "departments.avro",
    )
    restore, _, _ = make_restore(tmp_path)

    assert restore.run("departments") == 2
