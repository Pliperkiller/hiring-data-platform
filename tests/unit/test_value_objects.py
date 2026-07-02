from dataclasses import FrozenInstanceError
from datetime import UTC, datetime

import pytest

from app.domain.value_objects import (
    FieldError,
    HireDatetime,
    InvalidHireDatetimeFormat,
    ReasonCode,
    ValidatedHire,
    ValidationFailure,
)


@pytest.mark.parametrize(
    ("member", "expected"),
    [
        (ReasonCode.MISSING_ID, "MISSING_ID"),
        (ReasonCode.MISSING_NAME, "MISSING_NAME"),
        (ReasonCode.MISSING_DATETIME, "MISSING_DATETIME"),
        (ReasonCode.MISSING_DEPARTMENT, "MISSING_DEPARTMENT"),
        (ReasonCode.MISSING_JOB, "MISSING_JOB"),
        (ReasonCode.BAD_DATETIME_FORMAT, "BAD_DATETIME_FORMAT"),
        (ReasonCode.UNKNOWN_DEPARTMENT, "UNKNOWN_DEPARTMENT"),
        (ReasonCode.UNKNOWN_JOB, "UNKNOWN_JOB"),
    ],
)
def test_reason_code_values_match_catalog(member: ReasonCode, expected: str) -> None:
    assert member == expected


def test_hire_datetime_parse_accepts_valid_iso_z() -> None:
    parsed = HireDatetime.parse("2021-02-10T09:30:00Z")
    assert parsed.value == datetime(2021, 2, 10, 9, 30, tzinfo=UTC)


def test_hire_datetime_parse_result_is_tz_aware_utc() -> None:
    parsed = HireDatetime.parse("2021-02-10T09:30:00Z")
    assert parsed.value.utcoffset() == datetime(2021, 2, 10, tzinfo=UTC).utcoffset()


@pytest.mark.parametrize(
    "raw",
    [
        "2021-02-10 09:30:00Z",
        "2021-02-10T09:30:00+00:00",
        "2021-02-10T09:30:00",
        "2021-02-10T09:30:00.123Z",
        "2021-02-10t09:30:00z",
        "not-a-date",
        "",
    ],
)
def test_hire_datetime_parse_rejects_bad_formats(raw: str) -> None:
    with pytest.raises(InvalidHireDatetimeFormat):
        HireDatetime.parse(raw)


def test_hire_datetime_parse_rejects_invalid_calendar_date() -> None:
    with pytest.raises(InvalidHireDatetimeFormat):
        HireDatetime.parse("2021-02-30T09:30:00Z")


def test_field_error_is_immutable() -> None:
    error = FieldError(field="id", reason_code=ReasonCode.MISSING_ID, message="id is empty")
    with pytest.raises(FrozenInstanceError):
        error.message = "changed"  # type: ignore[misc]


def test_validated_hire_is_immutable() -> None:
    hire = ValidatedHire(
        id=1,
        name="Ada Lovelace",
        hire_datetime=HireDatetime.parse("2021-02-10T09:30:00Z"),
        department_id=1,
        job_id=5,
    )
    with pytest.raises(FrozenInstanceError):
        hire.name = "changed"  # type: ignore[misc]


def test_validation_failure_requires_at_least_one_error() -> None:
    with pytest.raises(ValueError, match="at least one"):
        ValidationFailure(errors=())


def test_validation_failure_holds_multiple_errors() -> None:
    errors = (
        FieldError(field="id", reason_code=ReasonCode.MISSING_ID, message="id is empty"),
        FieldError(field="name", reason_code=ReasonCode.MISSING_NAME, message="name is empty"),
    )
    failure = ValidationFailure(errors=errors)
    assert len(failure.errors) == 2
