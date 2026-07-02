"""IngestBatch use case: validate a batch, persist valid rows (upsert or SCD), log rejects.

Owns the transaction boundary: repositories only flush(); this use case commits once at the
end of a successful batch, and lets any unhandled exception propagate so the caller's session
rolls back instead of leaving a batch's failure half-persisted.

After that commit, the two report materialized views are refreshed in a second, separate
commit (see docs/DECISIONS.md). A refresh failure is logged and swallowed, never re-raised: if
it ran inside the batch's own transaction instead, a refresh error would abort that transaction
and roll back already-valid accepted rows, letting an unrelated reporting concern compromise
the ingestion guarantees CLAUDE.md mandates.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from app.domain.employee import Employee, EmployeeVersion, ScdAction, decide_scd_action
from app.domain.rejected_record import Load, RejectedRecord
from app.domain.repositories import (
    DepartmentRepository,
    EmployeeRepository,
    EmployeeVersionRepository,
    JobRepository,
    LoadRepository,
    RejectedRecordRepository,
    ReportRepository,
)
from app.domain.validation import ValidationService
from app.domain.value_objects import ValidatedHire, ValidationFailure

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class RejectedRow:
    """One field-level rejection, positioned within the submitted batch."""

    row_index: int
    field: str | None
    reason_code: str
    message: str


@dataclass(frozen=True, slots=True)
class IngestResult:
    load_id: int
    accepted: int
    rejected: int
    rejected_rows: tuple[RejectedRow, ...] = field(default_factory=tuple)


class IngestBatch:
    def __init__(
        self,
        department_repo: DepartmentRepository,
        job_repo: JobRepository,
        employee_repo: EmployeeRepository,
        employee_version_repo: EmployeeVersionRepository,
        load_repo: LoadRepository,
        rejected_record_repo: RejectedRecordRepository,
        report_repo: ReportRepository,
        validation_service: ValidationService,
        session: Session,
    ) -> None:
        self._department_repo = department_repo
        self._job_repo = job_repo
        self._employee_repo = employee_repo
        self._employee_version_repo = employee_version_repo
        self._load_repo = load_repo
        self._rejected_record_repo = rejected_record_repo
        self._report_repo = report_repo
        self._validation = validation_service
        self._session = session

    def ingest_departments(self, rows: list[dict[str, Any]]) -> IngestResult:
        return self._run_batch(
            target_table="departments",
            source="api:departments",
            rows=rows,
            validate=self._validation.validate_department,
            persist=lambda dept: self._department_repo.upsert(dept),
        )

    def ingest_jobs(self, rows: list[dict[str, Any]]) -> IngestResult:
        return self._run_batch(
            target_table="jobs",
            source="api:jobs",
            rows=rows,
            validate=self._validation.validate_job,
            persist=lambda job: self._job_repo.upsert(job),
        )

    def ingest_hires(self, rows: list[dict[str, Any]]) -> IngestResult:
        return self._run_batch(
            target_table="hired_employees",
            source="api:hired_employees",
            rows=rows,
            validate=self._validation.validate_hire,
            persist=self._persist_hire,
        )

    def _run_batch(
        self,
        *,
        target_table: str,
        source: str,
        rows: list[dict[str, Any]],
        validate: Callable[[dict[str, Any]], Any | ValidationFailure],
        persist: Callable[[Any], object],
    ) -> IngestResult:
        load = self._load_repo.create(Load(source=source))
        assert load.id is not None

        accepted = 0
        rejected = 0
        rejected_rows: list[RejectedRow] = []

        for row_index, row in enumerate(rows):
            result = validate(row)
            if isinstance(result, ValidationFailure):
                rejected += 1
                for error in result.errors:
                    self._rejected_record_repo.add(
                        RejectedRecord(
                            target_table=target_table,
                            raw_payload=row,
                            reason_code=error.reason_code,
                            message=error.message,
                            field=error.field,
                            load_id=load.id,
                        )
                    )
                    rejected_rows.append(
                        RejectedRow(
                            row_index=row_index,
                            field=error.field,
                            reason_code=error.reason_code.value,
                            message=error.message,
                        )
                    )
            else:
                persist(result)
                accepted += 1

        self._load_repo.mark_finished(load.id, accepted=accepted, rejected=rejected)
        self._session.commit()
        logger.info(
            "Load finished: source=%s load_id=%s accepted=%s rejected=%s",
            source,
            load.id,
            accepted,
            rejected,
        )

        try:
            self._report_repo.refresh_views()
            self._session.commit()
        except Exception:
            self._session.rollback()
            logger.warning("Materialized view refresh failed for load %s", load.id, exc_info=True)

        return IngestResult(
            load_id=load.id,
            accepted=accepted,
            rejected=rejected,
            rejected_rows=tuple(rejected_rows),
        )

    def _persist_hire(self, hire: ValidatedHire) -> None:
        exists = self._employee_repo.exists(hire.id)
        current = self._employee_version_repo.get_current(hire.id) if exists else None
        decision = decide_scd_action(
            employee_exists=exists,
            current_version=current,
            name=hire.name,
            department_id=hire.department_id,
            job_id=hire.job_id,
        )

        if decision.action is ScdAction.NEW_EMPLOYEE:
            self._employee_repo.add(
                Employee(
                    employee_id=hire.id,
                    name_at_hire=hire.name,
                    hire_datetime=hire.hire_datetime.value,
                    hire_department_id=hire.department_id,
                    hire_job_id=hire.job_id,
                    name=hire.name,
                    department_id=hire.department_id,
                    job_id=hire.job_id,
                )
            )
            self._employee_version_repo.add(
                EmployeeVersion(
                    employee_id=hire.id,
                    name=hire.name,
                    department_id=hire.department_id,
                    job_id=hire.job_id,
                    valid_from=hire.hire_datetime.value,
                    valid_to=None,
                    is_current=True,
                )
            )
        elif decision.action is ScdAction.NEW_VERSION:
            now = datetime.now(UTC)
            self._employee_version_repo.close_current(hire.id, valid_to=now)
            self._employee_version_repo.add(
                EmployeeVersion(
                    employee_id=hire.id,
                    name=hire.name,
                    department_id=hire.department_id,
                    job_id=hire.job_id,
                    valid_from=now,
                    valid_to=None,
                    is_current=True,
                )
            )
            # Keep employees' current name/department/job in sync with the new version, so a
            # caller can read "what is this employee's status right now" without a join — the
            # hire_* fields above are untouched, preserving hire-time report attribution.
            self._employee_repo.update_current(
                hire.id, name=hire.name, department_id=hire.department_id, job_id=hire.job_id
            )
        # ScdAction.NO_OP: nothing to do — identical re-upload.


__all__ = ["IngestBatch", "IngestResult", "RejectedRow"]
