from typing import Any

import pytest

from app.domain.reference import Department, Job
from app.domain.repositories import DepartmentRepository, JobRepository
from app.domain.validation import ValidationService
from app.domain.value_objects import HireDatetime, ReasonCode, ValidatedHire, ValidationFailure


class FakeDepartmentRepository(DepartmentRepository):
    def __init__(self, existing_ids: set[int]) -> None:
        self._ids = existing_ids

    def exists(self, department_id: int) -> bool:
        return department_id in self._ids

    def upsert(self, department: Department) -> Department:
        raise NotImplementedError

    def get(self, department_id: int) -> Department | None:
        raise NotImplementedError

    def list_all(self) -> list[Department]:
        raise NotImplementedError


class FakeJobRepository(JobRepository):
    def __init__(self, existing_ids: set[int]) -> None:
        self._ids = existing_ids

    def exists(self, job_id: int) -> bool:
        return job_id in self._ids

    def upsert(self, job: Job) -> Job:
        raise NotImplementedError

    def get(self, job_id: int) -> Job | None:
        raise NotImplementedError

    def list_all(self) -> list[Job]:
        raise NotImplementedError


def make_service(
    department_ids: set[int] | None = None, job_ids: set[int] | None = None
) -> ValidationService:
    return ValidationService(
        department_repo=FakeDepartmentRepository(department_ids or {1}),
        job_repo=FakeJobRepository(job_ids or {5}),
    )


def make_department_row(**overrides: Any) -> dict[str, Any]:
    row: dict[str, Any] = {"id": 1, "department": "Engineering"}
    row.update(overrides)
    return row


def make_job_row(**overrides: Any) -> dict[str, Any]:
    row: dict[str, Any] = {"id": 1, "job": "Recruiter"}
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


def error_codes(failure: ValidationFailure) -> set[ReasonCode]:
    return {error.reason_code for error in failure.errors}


def error_fields(failure: ValidationFailure) -> set[str]:
    return {error.field for error in failure.errors}


# --- departments ---


def test_validate_department_valid_row_passes() -> None:
    result = make_service().validate_department(make_department_row())
    assert result == Department(id=1, name="Engineering")


def test_validate_department_missing_id() -> None:
    row = make_department_row()
    del row["id"]
    result = make_service().validate_department(row)
    assert isinstance(result, ValidationFailure)
    assert error_codes(result) == {ReasonCode.MISSING_ID}


def test_validate_department_id_as_string_is_missing_id() -> None:
    result = make_service().validate_department(make_department_row(id="1"))
    assert isinstance(result, ValidationFailure)
    assert error_codes(result) == {ReasonCode.MISSING_ID}


def test_validate_department_id_as_bool_is_missing_id() -> None:
    result = make_service().validate_department(make_department_row(id=True))
    assert isinstance(result, ValidationFailure)
    assert error_codes(result) == {ReasonCode.MISSING_ID}


def test_validate_department_missing_name() -> None:
    row = make_department_row()
    del row["department"]
    result = make_service().validate_department(row)
    assert isinstance(result, ValidationFailure)
    assert error_codes(result) == {ReasonCode.MISSING_NAME}
    assert error_fields(result) == {"department"}


def test_validate_department_whitespace_name_is_missing_name() -> None:
    result = make_service().validate_department(make_department_row(department="   "))
    assert isinstance(result, ValidationFailure)
    assert error_codes(result) == {ReasonCode.MISSING_NAME}


def test_validate_department_multiple_defects() -> None:
    row = make_department_row(id="1", department="")
    result = make_service().validate_department(row)
    assert isinstance(result, ValidationFailure)
    assert len(result.errors) == 2
    assert error_codes(result) == {ReasonCode.MISSING_ID, ReasonCode.MISSING_NAME}


# --- jobs ---


def test_validate_job_valid_row_passes() -> None:
    result = make_service().validate_job(make_job_row())
    assert result == Job(id=1, name="Recruiter")


def test_validate_job_missing_id() -> None:
    row = make_job_row()
    del row["id"]
    result = make_service().validate_job(row)
    assert isinstance(result, ValidationFailure)
    assert error_codes(result) == {ReasonCode.MISSING_ID}


def test_validate_job_id_as_string_is_missing_id() -> None:
    result = make_service().validate_job(make_job_row(id="1"))
    assert isinstance(result, ValidationFailure)
    assert error_codes(result) == {ReasonCode.MISSING_ID}


def test_validate_job_id_as_bool_is_missing_id() -> None:
    result = make_service().validate_job(make_job_row(id=False))
    assert isinstance(result, ValidationFailure)
    assert error_codes(result) == {ReasonCode.MISSING_ID}


def test_validate_job_missing_name() -> None:
    row = make_job_row()
    del row["job"]
    result = make_service().validate_job(row)
    assert isinstance(result, ValidationFailure)
    assert error_codes(result) == {ReasonCode.MISSING_NAME}
    assert error_fields(result) == {"job"}


def test_validate_job_whitespace_name_is_missing_name() -> None:
    result = make_service().validate_job(make_job_row(job="   "))
    assert isinstance(result, ValidationFailure)
    assert error_codes(result) == {ReasonCode.MISSING_NAME}


def test_validate_job_multiple_defects() -> None:
    row = make_job_row(id="1", job="")
    result = make_service().validate_job(row)
    assert isinstance(result, ValidationFailure)
    assert len(result.errors) == 2
    assert error_codes(result) == {ReasonCode.MISSING_ID, ReasonCode.MISSING_NAME}


# --- hired_employees ---


def test_validate_hire_valid_row_passes() -> None:
    result = make_service().validate_hire(make_hire_row())
    assert result == ValidatedHire(
        id=101,
        name="Ada Lovelace",
        hire_datetime=HireDatetime.parse("2021-02-10T09:30:00Z"),
        department_id=1,
        job_id=5,
    )


def test_validate_hire_missing_id() -> None:
    row = make_hire_row()
    del row["id"]
    result = make_service().validate_hire(row)
    assert isinstance(result, ValidationFailure)
    assert error_codes(result) == {ReasonCode.MISSING_ID}


def test_validate_hire_id_wrong_type() -> None:
    result = make_service().validate_hire(make_hire_row(id="101"))
    assert isinstance(result, ValidationFailure)
    assert error_codes(result) == {ReasonCode.MISSING_ID}


def test_validate_hire_id_bool_rejected() -> None:
    result = make_service().validate_hire(make_hire_row(id=True))
    assert isinstance(result, ValidationFailure)
    assert error_codes(result) == {ReasonCode.MISSING_ID}


def test_validate_hire_missing_name() -> None:
    row = make_hire_row()
    del row["name"]
    result = make_service().validate_hire(row)
    assert isinstance(result, ValidationFailure)
    assert error_codes(result) == {ReasonCode.MISSING_NAME}


def test_validate_hire_whitespace_name_rejected() -> None:
    result = make_service().validate_hire(make_hire_row(name="   "))
    assert isinstance(result, ValidationFailure)
    assert error_codes(result) == {ReasonCode.MISSING_NAME}


def test_validate_hire_missing_datetime() -> None:
    row = make_hire_row()
    del row["datetime"]
    result = make_service().validate_hire(row)
    assert isinstance(result, ValidationFailure)
    assert error_codes(result) == {ReasonCode.MISSING_DATETIME}


@pytest.mark.parametrize(
    "raw",
    ["2021-02-10 09:30:00Z", "2021-02-10T09:30:00+00:00", "not-a-date"],
)
def test_validate_hire_bad_datetime_format(raw: str) -> None:
    result = make_service().validate_hire(make_hire_row(datetime=raw))
    assert isinstance(result, ValidationFailure)
    assert error_codes(result) == {ReasonCode.BAD_DATETIME_FORMAT}


def test_validate_hire_missing_department_id() -> None:
    row = make_hire_row()
    del row["department_id"]
    result = make_service().validate_hire(row)
    assert isinstance(result, ValidationFailure)
    assert error_codes(result) == {ReasonCode.MISSING_DEPARTMENT}


def test_validate_hire_department_id_wrong_type() -> None:
    result = make_service().validate_hire(make_hire_row(department_id="1"))
    assert isinstance(result, ValidationFailure)
    assert error_codes(result) == {ReasonCode.MISSING_DEPARTMENT}


def test_validate_hire_missing_job_id() -> None:
    row = make_hire_row()
    del row["job_id"]
    result = make_service().validate_hire(row)
    assert isinstance(result, ValidationFailure)
    assert error_codes(result) == {ReasonCode.MISSING_JOB}


def test_validate_hire_job_id_wrong_type() -> None:
    result = make_service().validate_hire(make_hire_row(job_id="5"))
    assert isinstance(result, ValidationFailure)
    assert error_codes(result) == {ReasonCode.MISSING_JOB}


def test_validate_hire_unknown_department() -> None:
    result = make_service().validate_hire(make_hire_row(department_id=999))
    assert isinstance(result, ValidationFailure)
    assert error_codes(result) == {ReasonCode.UNKNOWN_DEPARTMENT}
    assert "999" in result.errors[0].message


def test_validate_hire_unknown_job() -> None:
    result = make_service().validate_hire(make_hire_row(job_id=999))
    assert isinstance(result, ValidationFailure)
    assert error_codes(result) == {ReasonCode.UNKNOWN_JOB}


def test_validate_hire_unknown_department_and_unknown_job_both_reported() -> None:
    row = make_hire_row(department_id=999, job_id=888)
    result = make_service().validate_hire(row)
    assert isinstance(result, ValidationFailure)
    assert len(result.errors) == 2
    assert error_codes(result) == {ReasonCode.UNKNOWN_DEPARTMENT, ReasonCode.UNKNOWN_JOB}


def test_validate_hire_type_defect_and_fk_defect_together() -> None:
    row = make_hire_row(name="", department_id=999)
    result = make_service().validate_hire(row)
    assert isinstance(result, ValidationFailure)
    assert len(result.errors) == 2
    assert error_codes(result) == {ReasonCode.MISSING_NAME, ReasonCode.UNKNOWN_DEPARTMENT}


def test_validate_hire_department_id_not_int_skips_fk_check() -> None:
    # department_id=1000000 is not in the fake repo's set, but the wrong-typed department_id
    # below must not reach exists() at all, so only MISSING_DEPARTMENT should be reported once.
    result = make_service(department_ids=set()).validate_hire(make_hire_row(department_id="1"))
    assert isinstance(result, ValidationFailure)
    assert len(result.errors) == 1
    assert error_codes(result) == {ReasonCode.MISSING_DEPARTMENT}
