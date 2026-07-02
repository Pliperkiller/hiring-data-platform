"""Employee aggregate: immutable hire facts, plus current state and SCD Type 2 version history.

Validation-rule ownership (required fields, ISO 8601 parsing, FK existence) belongs to
feature/validation. SCD transition orchestration (deciding when to open/close a version)
belongs to feature/ingestion-api: decide_scd_action() is the pure decision, applied by
app/application/ingest_batch.py.

Employee carries both the immutable hire fact (name_at_hire, hire_datetime,
hire_department_id, hire_job_id — set once, never changed) and the current state (name,
department_id, job_id — kept in sync with the current EmployeeVersion on every SCD
transition). Reports attribute hires by the hire-time fields, never the current ones — see
docs/DECISIONS.md.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum, auto


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
    """Aggregate root: immutable hire facts plus current state.

    name_at_hire/hire_datetime/hire_department_id/hire_job_id are set once, at first load, and
    never change. name/department_id/job_id track the employee's current state — updated
    alongside the current EmployeeVersion on every SCD transition (see IngestBatch._persist_hire),
    so they always equal the current version's attributes, without a join.
    """

    employee_id: int
    name_at_hire: str
    hire_datetime: datetime
    hire_department_id: int
    hire_job_id: int
    name: str
    department_id: int
    job_id: int
    first_loaded_at: datetime | None = None


class ScdAction(Enum):
    """The three possible outcomes of ingesting one validated hire row."""

    NEW_EMPLOYEE = auto()
    NEW_VERSION = auto()
    NO_OP = auto()


@dataclass(frozen=True, slots=True)
class ScdDecision:
    """Pure outcome of comparing a validated hire against current state.

    current_version is only populated for NEW_VERSION (the version being closed) — the caller
    already has it and can close-then-open without a second repo round trip.
    """

    action: ScdAction
    current_version: EmployeeVersion | None = None


def decide_scd_action(
    employee_exists: bool,
    current_version: EmployeeVersion | None,
    name: str,
    department_id: int,
    job_id: int,
) -> ScdDecision:
    """Pure SCD Type 2 decision: no I/O, no repos, no datetime.now().

    Takes the values the caller already fetched, rather than repos, so this stays testable
    without fakes/mocks. The caller (IngestBatch) fetches employee_exists/current_version and
    executes the decision (assigning valid_from/valid_to/now()) against the repos.
    """
    if not employee_exists:
        return ScdDecision(action=ScdAction.NEW_EMPLOYEE)
    assert current_version is not None, "existing employee must have a current version"
    if current_version.has_changed(name, department_id, job_id):
        return ScdDecision(action=ScdAction.NEW_VERSION, current_version=current_version)
    return ScdDecision(action=ScdAction.NO_OP)
