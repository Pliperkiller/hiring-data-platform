"""Shared in-memory fake repositories for Backup/Restore unit tests.

Not a test_*.py file, so pytest doesn't collect it directly. Mirrors the Fake*Repository
pattern in test_ingest_batch.py, extended with the truncate()/restore_all() methods this
phase adds, plus call tracking so tests can assert truncate-before-insert ordering.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from app.domain.employee import Employee, EmployeeVersion
from app.domain.reference import Department, Job
from app.domain.rejected_record import Load, LoadStats, RejectedRecord
from app.domain.repositories import (
    DepartmentRepository,
    EmployeeRepository,
    EmployeeVersionRepository,
    JobRepository,
    LoadRepository,
    RejectedRecordRepository,
    ReportRepository,
)


class FakeDepartmentRepository(DepartmentRepository):
    def __init__(self, existing: dict[int, Department] | None = None) -> None:
        self._by_id: dict[int, Department] = dict(existing or {})
        self.truncate_called = False

    def upsert(self, department: Department) -> Department:
        self._by_id[department.id] = department
        return department

    def get(self, department_id: int) -> Department | None:
        return self._by_id.get(department_id)

    def list_all(self) -> list[Department]:
        return list(self._by_id.values())

    def exists(self, department_id: int) -> bool:
        return department_id in self._by_id

    def truncate(self) -> None:
        self.truncate_called = True
        self._by_id.clear()


class FakeJobRepository(JobRepository):
    def __init__(self, existing: dict[int, Job] | None = None) -> None:
        self._by_id: dict[int, Job] = dict(existing or {})
        self.truncate_called = False

    def upsert(self, job: Job) -> Job:
        self._by_id[job.id] = job
        return job

    def get(self, job_id: int) -> Job | None:
        return self._by_id.get(job_id)

    def list_all(self) -> list[Job]:
        return list(self._by_id.values())

    def exists(self, job_id: int) -> bool:
        return job_id in self._by_id

    def truncate(self) -> None:
        self.truncate_called = True
        self._by_id.clear()


class FakeEmployeeRepository(EmployeeRepository):
    def __init__(self, existing: dict[int, Employee] | None = None) -> None:
        self._by_id: dict[int, Employee] = dict(existing or {})
        self.truncate_called = False

    def add(self, employee: Employee) -> Employee:
        self._by_id[employee.employee_id] = employee
        return employee

    def get(self, employee_id: int) -> Employee | None:
        return self._by_id.get(employee_id)

    def exists(self, employee_id: int) -> bool:
        return employee_id in self._by_id

    def list_all(self) -> list[Employee]:
        return list(self._by_id.values())

    def truncate(self) -> None:
        self.truncate_called = True
        self._by_id.clear()


class FakeEmployeeVersionRepository(EmployeeVersionRepository):
    def __init__(self, existing: list[EmployeeVersion] | None = None) -> None:
        self._versions: list[EmployeeVersion] = list(existing or [])
        self.truncate_called = False
        self.restore_all_calls: list[list[EmployeeVersion]] = []

    def add(self, version: EmployeeVersion) -> EmployeeVersion:
        self._versions.append(version)
        return version

    def get_current(self, employee_id: int) -> EmployeeVersion | None:
        for version in self._versions:
            if version.employee_id == employee_id and version.is_current:
                return version
        return None

    def list_for_employee(self, employee_id: int) -> list[EmployeeVersion]:
        return [v for v in self._versions if v.employee_id == employee_id]

    def close_current(self, employee_id: int, valid_to: object) -> None:
        raise NotImplementedError("not exercised by backup/restore tests")

    def list_all(self) -> list[EmployeeVersion]:
        return list(self._versions)

    def truncate(self) -> None:
        self.truncate_called = True
        self._versions.clear()

    def restore_all(self, versions: list[EmployeeVersion]) -> None:
        self.restore_all_calls.append(list(versions))
        self._versions.extend(versions)


class FakeLoadRepository(LoadRepository):
    def __init__(self, existing: list[Load] | None = None) -> None:
        self._loads: list[Load] = list(existing or [])
        self.truncate_called = False
        self.restore_all_calls: list[list[Load]] = []

    def create(self, load: Load) -> Load:
        self._loads.append(load)
        return load

    def get(self, load_id: int) -> Load | None:
        for load in self._loads:
            if load.id == load_id:
                return load
        return None

    def mark_finished(self, load_id: int, accepted: int, rejected: int) -> Load:
        raise NotImplementedError("not exercised by backup/restore tests")

    def list_all(self) -> list[Load]:
        return list(self._loads)

    def recent_stats(self, since: datetime) -> LoadStats:
        finished = [
            load
            for load in self._loads
            if load.finished_at is not None
            and load.started_at is not None
            and load.started_at >= since
        ]
        return LoadStats.compute(
            total_loads=len(finished),
            total_accepted=sum(load.accepted for load in finished),
            total_rejected=sum(load.rejected for load in finished),
        )

    def truncate(self) -> None:
        self.truncate_called = True
        self._loads.clear()

    def restore_all(self, loads: list[Load]) -> None:
        self.restore_all_calls.append(list(loads))
        self._loads.extend(loads)


class FakeRejectedRecordRepository(RejectedRecordRepository):
    def __init__(self, existing: list[RejectedRecord] | None = None) -> None:
        self._records: list[RejectedRecord] = list(existing or [])
        self.truncate_called = False
        self.restore_all_calls: list[list[RejectedRecord]] = []

    def add(self, record: RejectedRecord) -> RejectedRecord:
        self._records.append(record)
        return record

    def list_for_load(self, load_id: int) -> list[RejectedRecord]:
        return [r for r in self._records if r.load_id == load_id]

    def list_all(self) -> list[RejectedRecord]:
        return list(self._records)

    def truncate(self) -> None:
        self.truncate_called = True
        self._records.clear()

    def restore_all(self, records: list[RejectedRecord]) -> None:
        self.restore_all_calls.append(list(records))
        self._records.extend(records)


class FakeReportRepository(ReportRepository):
    def __init__(self) -> None:
        self.refresh_calls = 0

    def refresh_views(self) -> None:
        self.refresh_calls += 1

    def list_hires_by_quarter(self) -> list[Any]:
        return []

    def list_departments_above_average(self) -> list[Any]:
        return []


class FakeSession:
    def __init__(self) -> None:
        self.commit_count = 0
        self.rollback_count = 0

    def commit(self) -> None:
        self.commit_count += 1

    def rollback(self) -> None:
        self.rollback_count += 1
