"""GenerateReport use case: read the two report materialized views.

No filtering here — the views already encode the year filter and the "valid records only by
construction" guarantee (see docs/DECISIONS.md).
"""

from __future__ import annotations

from app.domain.report import DepartmentAboveAverageRow, HireByQuarterRow
from app.domain.repositories import ReportRepository


class GenerateReport:
    def __init__(self, report_repo: ReportRepository) -> None:
        self._report_repo = report_repo

    def hires_by_quarter(self) -> list[HireByQuarterRow]:
        return self._report_repo.list_hires_by_quarter()

    def departments_above_average(self) -> list[DepartmentAboveAverageRow]:
        return self._report_repo.list_departments_above_average()


__all__ = ["GenerateReport"]
