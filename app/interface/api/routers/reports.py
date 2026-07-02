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


@router.get(
    "/hires-by-quarter",
    response_model=list[HiresByQuarterOut],
    summary="Hires by department, job, and quarter (2021)",
    description=(
        "Quarterly hire counts per department/job combination, filtered to 2021 (the year "
        "filter is mandatory — see docs/DECISIONS.md). Only combinations with at least one "
        "2021 hire are returned; a zero in a shown row's quarter is fine."
    ),
)
def get_hires_by_quarter(session: Session = Depends(get_db)) -> list[HiresByQuarterOut]:
    use_case = _build_use_case(session)
    rows = use_case.hires_by_quarter()
    return [
        HiresByQuarterOut(
            department=r.department, job=r.job, Q1=r.q1, Q2=r.q2, Q3=r.q3, Q4=r.q4
        )
        for r in rows
    ]


@router.get(
    "/departments-above-average",
    response_model=list[DepartmentAboveAverageOut],
    summary="Departments hiring above the 2021 average",
    description=(
        "Departments whose 2021 hire count exceeds the average across departments that "
        "hired in 2021, ordered by hired count descending."
    ),
)
def get_departments_above_average(
    session: Session = Depends(get_db),
) -> list[DepartmentAboveAverageOut]:
    use_case = _build_use_case(session)
    rows = use_case.departments_above_average()
    return [
        DepartmentAboveAverageOut(id=r.id, department=r.department, hired=r.hired)
        for r in rows
    ]
