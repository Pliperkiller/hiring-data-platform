"""Unit tests for the Reset use case's orchestration, against fake repositories (no DB)."""

from __future__ import annotations

from app.application.reset import Reset
from tests.unit.fakes import (
    FakeDepartmentRepository,
    FakeEmployeeRepository,
    FakeEmployeeVersionRepository,
    FakeJobRepository,
    FakeLoadRepository,
    FakeRejectedRecordRepository,
    FakeReportRepository,
    FakeSession,
)


def make_reset() -> tuple[
    Reset,
    FakeDepartmentRepository,
    FakeJobRepository,
    FakeEmployeeRepository,
    FakeEmployeeVersionRepository,
    FakeLoadRepository,
    FakeRejectedRecordRepository,
    FakeReportRepository,
    FakeSession,
]:
    department_repo = FakeDepartmentRepository()
    job_repo = FakeJobRepository()
    employee_repo = FakeEmployeeRepository()
    employee_version_repo = FakeEmployeeVersionRepository()
    load_repo = FakeLoadRepository()
    rejected_record_repo = FakeRejectedRecordRepository()
    report_repo = FakeReportRepository()
    session = FakeSession()
    reset = Reset(
        department_repo=department_repo,
        job_repo=job_repo,
        employee_repo=employee_repo,
        employee_version_repo=employee_version_repo,
        load_repo=load_repo,
        rejected_record_repo=rejected_record_repo,
        report_repo=report_repo,
        session=session,  # type: ignore[arg-type]
    )
    return (
        reset,
        department_repo,
        job_repo,
        employee_repo,
        employee_version_repo,
        load_repo,
        rejected_record_repo,
        report_repo,
        session,
    )


def test_run_truncates_all_six_repositories() -> None:
    (
        reset,
        department_repo,
        job_repo,
        employee_repo,
        employee_version_repo,
        load_repo,
        rejected_record_repo,
        _report_repo,
        _session,
    ) = make_reset()

    reset.run()

    assert department_repo.truncate_called is True
    assert job_repo.truncate_called is True
    assert employee_repo.truncate_called is True
    assert employee_version_repo.truncate_called is True
    assert load_repo.truncate_called is True
    assert rejected_record_repo.truncate_called is True


def test_run_refreshes_views_once_and_commits_once() -> None:
    reset, *_repos, report_repo, session = make_reset()

    reset.run()

    assert report_repo.refresh_calls == 1
    assert session.commit_count == 1
