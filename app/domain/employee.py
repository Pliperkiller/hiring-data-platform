"""Employee aggregate: immutable hire facts, plus SCD Type 2 version history.

Validation-rule ownership (required fields, ISO 8601 parsing, FK existence) belongs to
feature/validation. SCD transition orchestration (deciding when to open/close a version)
belongs to feature/ingestion-api. This module only holds the shapes and pure predicates.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class EmployeeVersion:
    """One SCD Type 2 row: the tracked attributes of an employee for a validity window."""

    employee_id: int
    name: str
    department_id: int
    job_id: int
    valid_from: datetime
    valid_to: datetime | None
    is_current: bool
    version_id: int | None = None

    @property
    def tracked_attributes(self) -> tuple[str, int, int]:
        """The attributes SCD2 tracks for change detection: (name, department_id, job_id)."""
        return (self.name, self.department_id, self.job_id)

    def has_changed(self, name: str, department_id: int, job_id: int) -> bool:
        return self.tracked_attributes != (name, department_id, job_id)


@dataclass(frozen=True, slots=True)
class Employee:
    """Aggregate root: hire facts, immutable after first load."""

    employee_id: int
    name_at_hire: str
    hire_datetime: datetime
    hire_department_id: int
    hire_job_id: int
    first_loaded_at: datetime | None = None
