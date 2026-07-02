"""POST /ingest/{table} routers (docs/API_CONTRACT.md)."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.application.ingest_batch import IngestBatch, IngestResult
from app.domain.validation import ValidationService
from app.infrastructure.db.repositories import (
    SqlAlchemyDepartmentRepository,
    SqlAlchemyEmployeeRepository,
    SqlAlchemyEmployeeVersionRepository,
    SqlAlchemyJobRepository,
    SqlAlchemyLoadRepository,
    SqlAlchemyRejectedRecordRepository,
)
from app.interface.api.dependencies import get_db
from app.interface.api.schemas import (
    DepartmentBatch,
    HireBatch,
    IngestResponse,
    JobBatch,
    RejectedRowOut,
)

router = APIRouter(prefix="/ingest", tags=["ingest"])


def _build_use_case(session: Session) -> IngestBatch:
    department_repo = SqlAlchemyDepartmentRepository(session)
    job_repo = SqlAlchemyJobRepository(session)
    return IngestBatch(
        department_repo=department_repo,
        job_repo=job_repo,
        employee_repo=SqlAlchemyEmployeeRepository(session),
        employee_version_repo=SqlAlchemyEmployeeVersionRepository(session),
        load_repo=SqlAlchemyLoadRepository(session),
        rejected_record_repo=SqlAlchemyRejectedRecordRepository(session),
        validation_service=ValidationService(department_repo=department_repo, job_repo=job_repo),
        session=session,
    )


def _to_response(result: IngestResult) -> IngestResponse:
    return IngestResponse(
        load_id=result.load_id,
        accepted=result.accepted,
        rejected=result.rejected,
        rejected_rows=[
            RejectedRowOut(
                row_index=r.row_index,
                field=r.field,
                reason_code=r.reason_code,
                message=r.message,
            )
            for r in result.rejected_rows
        ],
    )


@router.post("/departments", response_model=IngestResponse)
def ingest_departments(
    rows: DepartmentBatch, session: Session = Depends(get_db)
) -> IngestResponse:
    use_case = _build_use_case(session)
    result = use_case.ingest_departments([r.model_dump() for r in rows])
    return _to_response(result)


@router.post("/jobs", response_model=IngestResponse)
def ingest_jobs(rows: JobBatch, session: Session = Depends(get_db)) -> IngestResponse:
    use_case = _build_use_case(session)
    result = use_case.ingest_jobs([r.model_dump() for r in rows])
    return _to_response(result)


@router.post("/hired_employees", response_model=IngestResponse)
def ingest_hired_employees(
    rows: HireBatch, session: Session = Depends(get_db)
) -> IngestResponse:
    use_case = _build_use_case(session)
    result = use_case.ingest_hires([r.model_dump() for r in rows])
    return _to_response(result)
