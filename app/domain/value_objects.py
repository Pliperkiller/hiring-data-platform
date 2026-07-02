"""HireDatetime, ReasonCode, and the validation-outcome value objects.

ReasonCode is the closed reason-code catalog from docs/DATA_MODEL.md. HireDatetime parses and
validates ISO 8601 with Z, rejecting any other (even otherwise-valid) ISO 8601 variant, per the
"strict everywhere the data allows it for free" decision in docs/DECISIONS.md. FieldError and
ValidationFailure carry the field-level rejection reasons the validation service (validation.py)
produces; ValidatedHire is the typed output for an accepted hired_employees row.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class ReasonCode(StrEnum):
    MISSING_ID = "MISSING_ID"
    MISSING_NAME = "MISSING_NAME"
    MISSING_DATETIME = "MISSING_DATETIME"
    MISSING_DEPARTMENT = "MISSING_DEPARTMENT"
    MISSING_JOB = "MISSING_JOB"
    BAD_DATETIME_FORMAT = "BAD_DATETIME_FORMAT"
    UNKNOWN_DEPARTMENT = "UNKNOWN_DEPARTMENT"
    UNKNOWN_JOB = "UNKNOWN_JOB"


class InvalidHireDatetimeFormat(ValueError):
    """Raised by HireDatetime.parse() for anything not exact ISO 8601 with Z."""


_ISO8601_Z_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")


@dataclass(frozen=True, slots=True)
class HireDatetime:
    """A hire datetime, guaranteed to have been exact ISO 8601 with a literal Z on input."""

    value: datetime

    @staticmethod
    def parse(raw: str) -> HireDatetime:
        """Parse an exact `YYYY-MM-DDTHH:MM:SSZ` string.

        A regex gate runs before `datetime.fromisoformat` because that stdlib parser is more
        lenient than "exact ISO 8601 with Z" (e.g. it also accepts a space separator) — the
        regex enforces the exact shape, and `fromisoformat` still runs afterward to reject
        invalid calendar dates (e.g. day 30 in February) that the regex alone would not catch.
        """
        if not _ISO8601_Z_RE.match(raw):
            raise InvalidHireDatetimeFormat(raw)
        try:
            parsed = datetime.fromisoformat(raw)
        except ValueError as exc:
            raise InvalidHireDatetimeFormat(raw) from exc
        return HireDatetime(value=parsed)


@dataclass(frozen=True, slots=True)
class FieldError:
    """One field-level validation failure: which field, which reason, and a human message."""

    field: str
    reason_code: ReasonCode
    message: str


@dataclass(frozen=True, slots=True)
class ValidationFailure:
    """One or more FieldErrors for a single rejected row; never empty."""

    errors: tuple[FieldError, ...]

    def __post_init__(self) -> None:
        if not self.errors:
            raise ValueError("ValidationFailure requires at least one FieldError")


@dataclass(frozen=True, slots=True)
class ValidatedHire:
    """Typed values for an accepted hired_employees row.

    Deliberately not Employee/EmployeeVersion: those carry hire-fact/SCD-version semantics
    that Phase 3's ingestion use case decides (new employee vs. new version), not this
    validation service. department_id/job_id stay raw ints — only existence was checked here,
    not the full Department/Job entity.
    """

    id: int
    name: str
    hire_datetime: HireDatetime
    department_id: int
    job_id: int
