"""Unit tests for the AVRO write/read helpers and entity<->AVRO-dict conversion.

No DB: pure round trips through write_avro/read_avro against a tmp_path file, and the
per-table conversion functions applied to hand-built domain entities.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from app.domain.employee import Employee, EmployeeVersion
from app.domain.reference import Department, Job
from app.domain.rejected_record import Load, RejectedRecord
from app.domain.value_objects import ReasonCode
from app.infrastructure.avro import tables
from app.infrastructure.avro.codec import (
    avro_dict_to_department,
    avro_dict_to_employee,
    avro_dict_to_employee_version,
    avro_dict_to_job,
    avro_dict_to_load,
    avro_dict_to_rejected_record,
    department_to_avro_dict,
    employee_to_avro_dict,
    employee_version_to_avro_dict,
    job_to_avro_dict,
    load_to_avro_dict,
    read_avro,
    rejected_record_to_avro_dict,
    write_avro,
)

UTC_NOW = datetime(2021, 3, 15, 9, 30, 0, tzinfo=UTC)


def test_write_then_read_departments_round_trips(tmp_path: Path) -> None:
    dept = Department(id=1, name="Engineering")
    path = tmp_path / "departments.avro"

    write_avro("departments", [department_to_avro_dict(dept)], path)
    rows = read_avro(path)

    assert len(rows) == 1
    assert avro_dict_to_department(rows[0]) == dept


def test_write_then_read_jobs_round_trips(tmp_path: Path) -> None:
    job = Job(id=5, name="Recruiter")
    path = tmp_path / "jobs.avro"

    write_avro("jobs", [job_to_avro_dict(job)], path)
    rows = read_avro(path)

    assert avro_dict_to_job(rows[0]) == job


def test_write_then_read_employees_round_trips(tmp_path: Path) -> None:
    employee = Employee(
        employee_id=101,
        name_at_hire="Ada Lovelace",
        hire_datetime=UTC_NOW,
        hire_department_id=1,
        hire_job_id=5,
        first_loaded_at=UTC_NOW,
    )
    path = tmp_path / "employees.avro"

    write_avro("employees", [employee_to_avro_dict(employee)], path)
    rows = read_avro(path)

    assert avro_dict_to_employee(rows[0]) == employee


def test_write_then_read_employee_versions_round_trips(tmp_path: Path) -> None:
    version = EmployeeVersion(
        version_id=7,
        employee_id=101,
        name="Ada Lovelace",
        department_id=1,
        job_id=5,
        valid_from=UTC_NOW,
        valid_to=None,
        is_current=True,
    )
    path = tmp_path / "employee_versions.avro"

    write_avro("employee_versions", [employee_version_to_avro_dict(version)], path)
    rows = read_avro(path)

    assert avro_dict_to_employee_version(rows[0]) == version


def test_write_then_read_loads_round_trips(tmp_path: Path) -> None:
    load = Load(id=3, source="api:departments", started_at=UTC_NOW, finished_at=UTC_NOW)
    path = tmp_path / "loads.avro"

    write_avro("loads", [load_to_avro_dict(load)], path)
    rows = read_avro(path)

    assert avro_dict_to_load(rows[0]) == load


def test_write_then_read_rejected_records_round_trips(tmp_path: Path) -> None:
    record = RejectedRecord(
        id=9,
        target_table="departments",
        raw_payload={"id": "x"},
        reason_code=ReasonCode.MISSING_ID,
        message="id is empty",
        field="id",
        load_id=3,
        created_at=UTC_NOW,
    )
    path = tmp_path / "rejected_records.avro"

    write_avro("rejected_records", [rejected_record_to_avro_dict(record)], path)
    rows = read_avro(path)

    assert avro_dict_to_rejected_record(rows[0]) == record


def test_timestamp_millis_truncates_to_millisecond_precision(tmp_path: Path) -> None:
    micros_dt = datetime(2021, 3, 15, 9, 30, 0, 789456, tzinfo=UTC)
    load = Load(id=1, source="x", started_at=micros_dt, finished_at=None)
    path = tmp_path / "loads.avro"

    write_avro("loads", [load_to_avro_dict(load)], path)
    (row,) = read_avro(path)

    expected = micros_dt.replace(microsecond=(micros_dt.microsecond // 1000) * 1000)
    assert row["started_at"] == expected
    assert row["started_at"].tzinfo is not None


def test_nullable_columns_round_trip_null(tmp_path: Path) -> None:
    version = EmployeeVersion(
        version_id=1,
        employee_id=1,
        name="Alice",
        department_id=1,
        job_id=1,
        valid_from=UTC_NOW,
        valid_to=None,
        is_current=True,
    )
    load = Load(id=1, source="x", started_at=UTC_NOW, finished_at=None)
    record = RejectedRecord(
        id=1,
        target_table="departments",
        raw_payload={},
        reason_code=ReasonCode.MISSING_ID,
        message="msg",
        field=None,
        load_id=None,
        created_at=UTC_NOW,
    )

    version_path = tmp_path / "employee_versions.avro"
    write_avro("employee_versions", [employee_version_to_avro_dict(version)], version_path)
    (version_row,) = read_avro(version_path)
    assert version_row["valid_to"] is None

    load_path = tmp_path / "loads.avro"
    write_avro("loads", [load_to_avro_dict(load)], load_path)
    (load_row,) = read_avro(load_path)
    assert load_row["finished_at"] is None

    record_path = tmp_path / "rejected_records.avro"
    write_avro("rejected_records", [rejected_record_to_avro_dict(record)], record_path)
    (record_row,) = read_avro(record_path)
    assert record_row["field"] is None
    assert record_row["load_id"] is None


def test_nullable_columns_round_trip_present(tmp_path: Path) -> None:
    version = EmployeeVersion(
        version_id=1,
        employee_id=1,
        name="Alice",
        department_id=1,
        job_id=1,
        valid_from=UTC_NOW,
        valid_to=UTC_NOW,
        is_current=False,
    )
    load = Load(id=1, source="x", started_at=UTC_NOW, finished_at=UTC_NOW)
    record = RejectedRecord(
        id=1,
        target_table="departments",
        raw_payload={},
        reason_code=ReasonCode.MISSING_ID,
        message="msg",
        field="id",
        load_id=5,
        created_at=UTC_NOW,
    )

    version_path = tmp_path / "employee_versions.avro"
    write_avro("employee_versions", [employee_version_to_avro_dict(version)], version_path)
    (version_row,) = read_avro(version_path)
    assert version_row["valid_to"] is not None

    load_path = tmp_path / "loads.avro"
    write_avro("loads", [load_to_avro_dict(load)], load_path)
    (load_row,) = read_avro(load_path)
    assert load_row["finished_at"] is not None

    record_path = tmp_path / "rejected_records.avro"
    write_avro("rejected_records", [rejected_record_to_avro_dict(record)], record_path)
    (record_row,) = read_avro(record_path)
    assert record_row["field"] == "id"
    assert record_row["load_id"] == 5


def test_raw_payload_json_round_trips(tmp_path: Path) -> None:
    payload: dict[str, Any] = {
        "id": "5",
        "nested": {"a": [1, 2, 3]},
        "name": "Adaline Ünïcode",
    }
    record = RejectedRecord(
        id=1,
        target_table="hired_employees",
        raw_payload=payload,
        reason_code=ReasonCode.BAD_DATETIME_FORMAT,
        message="bad format",
        field="datetime",
        load_id=1,
        created_at=UTC_NOW,
    )
    path = tmp_path / "rejected_records.avro"

    write_avro("rejected_records", [rejected_record_to_avro_dict(record)], path)
    (row,) = read_avro(path)

    assert avro_dict_to_rejected_record(row).raw_payload == payload


def test_validate_table_name_rejects_unknown_table() -> None:
    with pytest.raises(ValueError):
        tables.validate_table_name("bogus")


def test_validate_table_name_accepts_all_known_tables() -> None:
    for table in tables.TABLE_NAMES:
        tables.validate_table_name(table)
