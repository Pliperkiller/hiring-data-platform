from app.application.generate_report import GenerateReport
from app.domain.report import DepartmentAboveAverageRow, HireByQuarterRow
from app.domain.repositories import ReportRepository


class FakeReportRepository(ReportRepository):
    def __init__(
        self,
        hires_by_quarter: list[HireByQuarterRow] | None = None,
        departments_above_average: list[DepartmentAboveAverageRow] | None = None,
    ) -> None:
        self._hires_by_quarter = hires_by_quarter or []
        self._departments_above_average = departments_above_average or []
        self.refresh_calls = 0

    def refresh_views(self) -> None:
        self.refresh_calls += 1

    def list_hires_by_quarter(self) -> list[HireByQuarterRow]:
        return self._hires_by_quarter

    def list_departments_above_average(self) -> list[DepartmentAboveAverageRow]:
        return self._departments_above_average


def test_hires_by_quarter_passes_through_repository_rows_unchanged() -> None:
    rows = [HireByQuarterRow(department="Engineering", job="Recruiter", q1=1, q2=0, q3=0, q4=0)]
    repo = FakeReportRepository(hires_by_quarter=rows)
    use_case = GenerateReport(report_repo=repo)

    result = use_case.hires_by_quarter()

    assert result == rows
    assert repo.refresh_calls == 0


def test_departments_above_average_passes_through_repository_rows_unchanged() -> None:
    rows = [DepartmentAboveAverageRow(id=1, department="Engineering", hired=205)]
    repo = FakeReportRepository(departments_above_average=rows)
    use_case = GenerateReport(report_repo=repo)

    result = use_case.departments_above_average()

    assert result == rows


def test_hires_by_quarter_returns_empty_list_when_no_data() -> None:
    use_case = GenerateReport(report_repo=FakeReportRepository())

    assert use_case.hires_by_quarter() == []
    assert use_case.departments_above_average() == []
