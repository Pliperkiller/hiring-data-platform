"""AVRO write/read helpers built on fastavro, and entity<->AVRO-dict conversion.

See docs/BACKUP_RESTORE.md for the type mapping. Timestamps use the `timestamp-millis`
logical type: fastavro transparently accepts and returns tz-aware `datetime` objects for it,
but truncates to millisecond precision (Postgres stores microseconds) — a deliberate,
spec-driven precision loss, not a bug. `raw_payload` (JSONB) is a JSON string field.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from datetime import datetime
from pathlib import Path
from typing import Any, cast

import fastavro

from app.domain.employee import Employee, EmployeeVersion
from app.domain.reference import Department, Job
from app.domain.rejected_record import Load, RejectedRecord
from app.domain.value_objects import ReasonCode
from app.infrastructure.avro.schemas import TABLE_SCHEMAS


def write_avro(table: str, rows: Iterable[dict[str, Any]], path: Path) -> None:
    """Serialize `rows` (already AVRO-ready dicts, see `*_to_avro_dict` below) to `path`."""
    schema = TABLE_SCHEMAS[table]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as fh:
        fastavro.writer(fh, schema, rows)


def read_avro(path: Path) -> list[dict[str, Any]]:
    """Deserialize an AVRO file back into a list of plain dicts (schema read from the file)."""
    with path.open("rb") as fh:
        return cast(list[dict[str, Any]], list(fastavro.reader(fh)))


def _require_utc(value: datetime | None, field: str) -> datetime | None:
    if value is not None and value.tzinfo is None:
        raise ValueError(f"{field} must be timezone-aware, got a naive datetime")
    return value


def department_to_avro_dict(department: Department) -> dict[str, Any]:
    return {"id": department.id, "name": department.name}


def avro_dict_to_department(row: dict[str, Any]) -> Department:
    return Department(id=row["id"], name=row["name"])


def job_to_avro_dict(job: Job) -> dict[str, Any]:
    return {"id": job.id, "name": job.name}


def avro_dict_to_job(row: dict[str, Any]) -> Job:
    return Job(id=row["id"], name=row["name"])


def employee_to_avro_dict(employee: Employee) -> dict[str, Any]:
    _require_utc(employee.hire_datetime, "hire_datetime")
    _require_utc(employee.first_loaded_at, "first_loaded_at")
    assert employee.first_loaded_at is not None
    return {
        "employee_id": employee.employee_id,
        "name_at_hire": employee.name_at_hire,
        "hire_datetime": employee.hire_datetime,
        "hire_department_id": employee.hire_department_id,
        "hire_job_id": employee.hire_job_id,
        "first_loaded_at": employee.first_loaded_at,
    }


def avro_dict_to_employee(row: dict[str, Any]) -> Employee:
    return Employee(
        employee_id=row["employee_id"],
        name_at_hire=row["name_at_hire"],
        hire_datetime=row["hire_datetime"],
        hire_department_id=row["hire_department_id"],
        hire_job_id=row["hire_job_id"],
        first_loaded_at=row["first_loaded_at"],
    )


def employee_version_to_avro_dict(version: EmployeeVersion) -> dict[str, Any]:
    _require_utc(version.valid_from, "valid_from")
    _require_utc(version.valid_to, "valid_to")
    assert version.version_id is not None
    return {
        "version_id": version.version_id,
        "employee_id": version.employee_id,
        "name": version.name,
        "department_id": version.department_id,
        "job_id": version.job_id,
        "valid_from": version.valid_from,
        "valid_to": version.valid_to,
        "is_current": version.is_current,
    }


def avro_dict_to_employee_version(row: dict[str, Any]) -> EmployeeVersion:
    return EmployeeVersion(
        version_id=row["version_id"],
        employee_id=row["employee_id"],
        name=row["name"],
        department_id=row["department_id"],
        job_id=row["job_id"],
        valid_from=row["valid_from"],
        valid_to=row["valid_to"],
        is_current=row["is_current"],
    )


def load_to_avro_dict(load: Load) -> dict[str, Any]:
    _require_utc(load.started_at, "started_at")
    _require_utc(load.finished_at, "finished_at")
    assert load.id is not None
    assert load.started_at is not None
    return {
        "id": load.id,
        "source": load.source,
        "started_at": load.started_at,
        "finished_at": load.finished_at,
        "accepted": load.accepted,
        "rejected": load.rejected,
    }


def avro_dict_to_load(row: dict[str, Any]) -> Load:
    return Load(
        id=row["id"],
        source=row["source"],
        started_at=row["started_at"],
        finished_at=row["finished_at"],
        accepted=row["accepted"],
        rejected=row["rejected"],
    )


def rejected_record_to_avro_dict(record: RejectedRecord) -> dict[str, Any]:
    _require_utc(record.created_at, "created_at")
    assert record.id is not None
    assert record.created_at is not None
    return {
        "id": record.id,
        "target_table": record.target_table,
        "raw_payload": json.dumps(record.raw_payload),
        "field": record.field,
        "reason_code": record.reason_code.value,
        "message": record.message,
        "load_id": record.load_id,
        "created_at": record.created_at,
    }


def avro_dict_to_rejected_record(row: dict[str, Any]) -> RejectedRecord:
    return RejectedRecord(
        id=row["id"],
        target_table=row["target_table"],
        raw_payload=json.loads(row["raw_payload"]),
        field=row["field"],
        reason_code=ReasonCode(row["reason_code"]),
        message=row["message"],
        load_id=row["load_id"],
        created_at=row["created_at"],
    )


def to_avro_dicts(table: str, rows: list[Any]) -> list[dict[str, Any]]:
    """Dispatch a list of domain entities to their AVRO-dict form, by table name."""
    if table == "departments":
        return [department_to_avro_dict(row) for row in rows]
    if table == "jobs":
        return [job_to_avro_dict(row) for row in rows]
    if table == "employees":
        return [employee_to_avro_dict(row) for row in rows]
    if table == "employee_versions":
        return [employee_version_to_avro_dict(row) for row in rows]
    if table == "loads":
        return [load_to_avro_dict(row) for row in rows]
    if table == "rejected_records":
        return [rejected_record_to_avro_dict(row) for row in rows]
    raise ValueError(f"unknown table {table!r}")


def from_avro_dicts(table: str, rows: list[dict[str, Any]]) -> list[Any]:
    """Dispatch a list of AVRO dicts back to domain entities, by table name."""
    if table == "departments":
        return [avro_dict_to_department(row) for row in rows]
    if table == "jobs":
        return [avro_dict_to_job(row) for row in rows]
    if table == "employees":
        return [avro_dict_to_employee(row) for row in rows]
    if table == "employee_versions":
        return [avro_dict_to_employee_version(row) for row in rows]
    if table == "loads":
        return [avro_dict_to_load(row) for row in rows]
    if table == "rejected_records":
        return [avro_dict_to_rejected_record(row) for row in rows]
    raise ValueError(f"unknown table {table!r}")
