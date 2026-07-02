"""GET /reports/* routers (docs/API_CONTRACT.md)."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.application.generate_report import GenerateReport
from app.infrastructure.db.repositories import SqlAlchemyReportRepository
from app.interface.api.dependencies import get_db
from app.interface.api.schemas import DepartmentAboveAverageOut, HiresByQuarterOut

router = APIRouter(prefix="/reports", tags=["reports"])


def _build_use_case(session: Session) -> GenerateReport:
    return GenerateReport(report_repo=SqlAlchemyReportRepository(session))


@router.get("/hires-by-quarter", response_model=list[HiresByQuarterOut])
def get_hires_by_quarter(session: Session = Depends(get_db)) -> list[HiresByQuarterOut]:
    use_case = _build_use_case(session)
    rows = use_case.hires_by_quarter()
    return [
        HiresByQuarterOut(
            department=r.department, job=r.job, Q1=r.q1, Q2=r.q2, Q3=r.q3, Q4=r.q4
        )
        for r in rows
    ]


@router.get("/departments-above-average", response_model=list[DepartmentAboveAverageOut])
def get_departments_above_average(
    session: Session = Depends(get_db),
) -> list[DepartmentAboveAverageOut]:
    use_case = _build_use_case(session)
    rows = use_case.departments_above_average()
    return [
        DepartmentAboveAverageOut(id=r.id, department=r.department, hired=r.hired)
        for r in rows
    ]
