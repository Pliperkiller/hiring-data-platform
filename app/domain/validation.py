"""Validation domain service.

Validates one raw row at a time for departments, jobs, and hired_employees, per the rules in
docs/DATA_MODEL.md and docs/DECISIONS.md: required fields, integer ids and FK ids (no string
coercion, bool excluded), exact ISO 8601 with Z for hire datetimes, and FK existence for
department_id/job_id. Never coerces invalid data — a row either validates cleanly into a typed
value or comes back as a ValidationFailure carrying every field-level defect found, so a row
with multiple simultaneous defects is fully reported rather than only its first bad field.

Row-batch orchestration (row_index, partial success, SCD versioning) is Phase 3's job; this
service only ever sees one row dict at a time and knows nothing about batches or persistence
beyond the read-only FK existence checks.
"""

from __future__ import annotations

from typing import Any

from app.domain.reference import Department, Job
from app.domain.repositories import DepartmentRepository, JobRepository
from app.domain.value_objects import (
    FieldError,
    HireDatetime,
    InvalidHireDatetimeFormat,
    ReasonCode,
    ValidatedHire,
    ValidationFailure,
)


def _check_id(row: dict[str, Any]) -> int | FieldError:
    value = row.get("id")
    if type(value) is not int:
        return FieldError("id", ReasonCode.MISSING_ID, "id is empty or not an integer")
    return value


def _check_name(row: dict[str, Any], key: str, reason_code: ReasonCode) -> str | FieldError:
    value = row.get(key)
    if not isinstance(value, str) or value.strip() == "":
        return FieldError(key, reason_code, f"{key} is empty")
    return value


def _check_fk_id(row: dict[str, Any], key: str, missing_code: ReasonCode) -> int | FieldError:
    value = row.get(key)
    if type(value) is not int:
        return FieldError(key, missing_code, f"{key} is empty or not an integer")
    return value


def _check_datetime(row: dict[str, Any]) -> HireDatetime | FieldError:
    value = row.get("datetime")
    if not isinstance(value, str) or value == "":
        return FieldError("datetime", ReasonCode.MISSING_DATETIME, "datetime is empty")
    try:
        return HireDatetime.parse(value)
    except InvalidHireDatetimeFormat:
        return FieldError(
            "datetime",
            ReasonCode.BAD_DATETIME_FORMAT,
            f"datetime '{value}' is not ISO 8601 with Z",
        )


class ValidationService:
    def __init__(self, department_repo: DepartmentRepository, job_repo: JobRepository) -> None:
        self._department_repo = department_repo
        self._job_repo = job_repo

    def validate_department(self, row: dict[str, Any]) -> Department | ValidationFailure:
        id_result = _check_id(row)
        name_result = _check_name(row, "department", ReasonCode.MISSING_NAME)

        errors = [r for r in (id_result, name_result) if isinstance(r, FieldError)]
        if errors:
            return ValidationFailure(errors=tuple(errors))

        assert isinstance(id_result, int)
        assert isinstance(name_result, str)
        return Department(id=id_result, name=name_result)

    def validate_job(self, row: dict[str, Any]) -> Job | ValidationFailure:
        id_result = _check_id(row)
        name_result = _check_name(row, "job", ReasonCode.MISSING_NAME)

        errors = [r for r in (id_result, name_result) if isinstance(r, FieldError)]
        if errors:
            return ValidationFailure(errors=tuple(errors))

        assert isinstance(id_result, int)
        assert isinstance(name_result, str)
        return Job(id=id_result, name=name_result)

    def validate_hire(self, row: dict[str, Any]) -> ValidatedHire | ValidationFailure:
        id_result = _check_id(row)
        name_result = _check_name(row, "name", ReasonCode.MISSING_NAME)
        datetime_result = _check_datetime(row)
        department_result = _check_fk_id(row, "department_id", ReasonCode.MISSING_DEPARTMENT)
        job_result = _check_fk_id(row, "job_id", ReasonCode.MISSING_JOB)

        errors = [
            r
            for r in (id_result, name_result, datetime_result, department_result, job_result)
            if isinstance(r, FieldError)
        ]

        if isinstance(department_result, int) and not self._department_repo.exists(
            department_result
        ):
            errors.append(
                FieldError(
                    "department_id",
                    ReasonCode.UNKNOWN_DEPARTMENT,
                    f"department_id {department_result} does not exist",
                )
            )
        if isinstance(job_result, int) and not self._job_repo.exists(job_result):
            errors.append(
                FieldError("job_id", ReasonCode.UNKNOWN_JOB, f"job_id {job_result} does not exist")
            )

        if errors:
            return ValidationFailure(errors=tuple(errors))

        assert isinstance(id_result, int)
        assert isinstance(name_result, str)
        assert isinstance(datetime_result, HireDatetime)
        assert isinstance(department_result, int)
        assert isinstance(job_result, int)
        return ValidatedHire(
            id=id_result,
            name=name_result,
            hire_datetime=datetime_result,
            department_id=department_result,
            job_id=job_result,
        )
