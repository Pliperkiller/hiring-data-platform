"""Reset use case: truncate all six tables and refresh the report views.

Admin operation, reachable only via `POST /admin/reset` (see docs/API_CONTRACT.md and
docs/DECISIONS.md) — this is the single most destructive action in the app, so unlike
Backup/Restore there is deliberately no CLI entry point, keeping it reachable only through the
password-gated Streamlit Admin tab or a direct API call.

Scope: this only empties the database tables and refreshes `report_hires_by_quarter` /
`report_departments_above_average`. It never touches `data/*.avro` — an existing backup survives
a reset untouched, since destroying it silently would be a surprising side effect of a DB reset.

Unlike `IngestBatch._run_batch`'s materialized-view refresh (app/application/ingest_batch.py),
which swallows a refresh failure so it never rolls back already-accepted rows, `Reset.run()` has
no such asymmetry: there is nothing else in the transaction worth protecting, so a refresh
failure is allowed to propagate and surface as a 500.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.domain.repositories import (
    DepartmentRepository,
    EmployeeRepository,
    EmployeeVersionRepository,
    JobRepository,
    LoadRepository,
    RejectedRecordRepository,
    ReportRepository,
)


class Reset:
    def __init__(
        self,
        department_repo: DepartmentRepository,
        job_repo: JobRepository,
        employee_repo: EmployeeRepository,
        employee_version_repo: EmployeeVersionRepository,
        load_repo: LoadRepository,
        rejected_record_repo: RejectedRecordRepository,
        report_repo: ReportRepository,
        session: Session,
    ) -> None:
        self._department_repo = department_repo
        self._job_repo = job_repo
        self._employee_repo = employee_repo
        self._employee_version_repo = employee_version_repo
        self._load_repo = load_repo
        self._rejected_record_repo = rejected_record_repo
        self._report_repo = report_repo
        self._session = session

    def run(self) -> None:
        # Truncation order doesn't matter: every table's truncate() is CASCADE (see
        # docs/DECISIONS.md), so cross-table FKs never block any ordering.
        self._department_repo.truncate()
        self._job_repo.truncate()
        self._employee_repo.truncate()
        self._employee_version_repo.truncate()
        self._load_repo.truncate()
        self._rejected_record_repo.truncate()
        self._report_repo.refresh_views()
        self._session.commit()


def _build_reset(session: Session) -> Reset:
    from app.infrastructure.db.repositories import (
        SqlAlchemyDepartmentRepository,
        SqlAlchemyEmployeeRepository,
        SqlAlchemyEmployeeVersionRepository,
        SqlAlchemyJobRepository,
        SqlAlchemyLoadRepository,
        SqlAlchemyRejectedRecordRepository,
        SqlAlchemyReportRepository,
    )

    return Reset(
        department_repo=SqlAlchemyDepartmentRepository(session),
        job_repo=SqlAlchemyJobRepository(session),
        employee_repo=SqlAlchemyEmployeeRepository(session),
        employee_version_repo=SqlAlchemyEmployeeVersionRepository(session),
        load_repo=SqlAlchemyLoadRepository(session),
        rejected_record_repo=SqlAlchemyRejectedRecordRepository(session),
        report_repo=SqlAlchemyReportRepository(session),
        session=session,
    )


__all__ = ["Reset"]
