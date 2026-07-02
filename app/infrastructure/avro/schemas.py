"""AVRO schema definitions for the six backed-up tables (docs/BACKUP_RESTORE.md).

Plain dict literals, not .avsc files: see docs/DECISIONS.md "AVRO schema representation."
Field order matches app/infrastructure/db/models.py column order for each table. Field names
match the domain entity attribute names (not the DB column names), since codec.py converts
directly between domain entities and these AVRO dicts.
"""

from __future__ import annotations

_TIMESTAMP_MILLIS = {"type": "long", "logicalType": "timestamp-millis"}
_NULLABLE_TIMESTAMP_MILLIS = ["null", _TIMESTAMP_MILLIS]

DEPARTMENT_SCHEMA = {
    "type": "record",
    "name": "Department",
    "fields": [
        {"name": "id", "type": "long"},
        {"name": "name", "type": "string"},
    ],
}

JOB_SCHEMA = {
    "type": "record",
    "name": "Job",
    "fields": [
        {"name": "id", "type": "long"},
        {"name": "name", "type": "string"},
    ],
}

EMPLOYEE_SCHEMA = {
    "type": "record",
    "name": "Employee",
    "fields": [
        {"name": "employee_id", "type": "long"},
        {"name": "name_at_hire", "type": "string"},
        {"name": "hire_datetime", "type": _TIMESTAMP_MILLIS},
        {"name": "hire_department_id", "type": "long"},
        {"name": "hire_job_id", "type": "long"},
        {"name": "first_loaded_at", "type": _TIMESTAMP_MILLIS},
    ],
}

EMPLOYEE_VERSION_SCHEMA = {
    "type": "record",
    "name": "EmployeeVersion",
    "fields": [
        {"name": "version_id", "type": "long"},
        {"name": "employee_id", "type": "long"},
        {"name": "name", "type": "string"},
        {"name": "department_id", "type": "long"},
        {"name": "job_id", "type": "long"},
        {"name": "valid_from", "type": _TIMESTAMP_MILLIS},
        {"name": "valid_to", "type": _NULLABLE_TIMESTAMP_MILLIS, "default": None},
        {"name": "is_current", "type": "boolean"},
    ],
}

LOAD_SCHEMA = {
    "type": "record",
    "name": "Load",
    "fields": [
        {"name": "id", "type": "long"},
        {"name": "source", "type": "string"},
        {"name": "started_at", "type": _TIMESTAMP_MILLIS},
        {"name": "finished_at", "type": _NULLABLE_TIMESTAMP_MILLIS, "default": None},
        {"name": "accepted", "type": "long"},
        {"name": "rejected", "type": "long"},
    ],
}

REJECTED_RECORD_SCHEMA = {
    "type": "record",
    "name": "RejectedRecord",
    "fields": [
        {"name": "id", "type": "long"},
        {"name": "target_table", "type": "string"},
        {"name": "raw_payload", "type": "string"},
        {"name": "field", "type": ["null", "string"], "default": None},
        {"name": "reason_code", "type": "string"},
        {"name": "message", "type": "string"},
        {"name": "load_id", "type": ["null", "long"], "default": None},
        {"name": "created_at", "type": _TIMESTAMP_MILLIS},
    ],
}

TABLE_SCHEMAS: dict[str, dict] = {
    "departments": DEPARTMENT_SCHEMA,
    "jobs": JOB_SCHEMA,
    "employees": EMPLOYEE_SCHEMA,
    "employee_versions": EMPLOYEE_VERSION_SCHEMA,
    "loads": LOAD_SCHEMA,
    "rejected_records": REJECTED_RECORD_SCHEMA,
}
