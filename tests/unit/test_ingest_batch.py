from dataclasses import dataclass, replace
from datetime import UTC, datetime
from typing import Any

from app.application.ingest_batch import IngestBatch
from app.domain.employee import Employee, EmployeeVersion
from app.domain.reference import Department, Job
from app.domain.rejected_record import Load, RejectedRecord
from app.domain.repositories import (
    DepartmentRepository,
    EmployeeRepository,
    EmployeeVersionRepository,
    JobRepository,
    LoadRepository,
    RejectedRecordRepository,
)
from app.domain.validation import ValidationService


class FakeDepartmentRepository(DepartmentRepository):
    def __init__(self, existing: dict[int, Department] | None = None) -> None:
        self._by_id: dict[int, Department] = dict(existing or {})

    def upsert(self, department: Department) -> Department:
        self._by_id[department.id] = department
        return department

    def get(self, department_id: int) -> Department | None:
        return self._by_id.get(department_id)

    def list_all(self) -> list[Department]:
        return list(self._by_id.values())

    def exists(self, department_id: int) -> bool:
        return department_id in self._by_id


class FakeJobRepository(JobRepository):
    def __init__(self, existing: dict[int, Job] | None = None) -> None:
        self._by_id: dict[int, Job] = dict(existing or {})

    def upsert(self, job: Job) -> Job:
        self._by_id[job.id] = job
        return job

    def get(self, job_id: int) -> Job | None:
        return self._by_id.get(job_id)

    def list_all(self) -> list[Job]:
        return list(self._by_id.values())

    def exists(self, job_id: int) -> bool:
        return job_id in self._by_id


class FakeEmployeeRepository(EmployeeRepository):
    def __init__(self) -> None:
        self._by_id: dict[int, Employee] = {}
        self.add_calls: list[Employee] = []

    def add(self, employee: Employee) -> Employee:
        self._by_id[employee.employee_id] = employee
        self.add_calls.append(employee)
        return employee

    def get(self, employee_id: int) -> Employee | None:
        return self._by_id.get(employee_id)

    def exists(self, employee_id: int) -> bool:
        return employee_id in self._by_id

    def list_all(self) -> list[Employee]:
        return list(self._by_id.values())


class FakeEmployeeVersionRepository(EmployeeVersionRepository):
    def __init__(self) -> None:
        self._versions: list[EmployeeVersion] = []
        self._next_id = 1
        self.close_current_calls: list[int] = []

    def add(self, version: EmployeeVersion) -> EmployeeVersion:
        stored = replace(version, version_id=self._next_id)
        self._next_id += 1
        self._versions.append(stored)
        return stored

    def get_current(self, employee_id: int) -> EmployeeVersion | None:
        for version in self._versions:
            if version.employee_id == employee_id and version.is_current:
                return version
        return None

    def list_for_employee(self, employee_id: int) -> list[EmployeeVersion]:
        return [v for v in self._versions if v.employee_id == employee_id]

    def close_current(self, employee_id: int, valid_to: datetime) -> None:
        self.close_current_calls.append(employee_id)
        for index, version in enumerate(self._versions):
            if version.employee_id == employee_id and version.is_current:
                self._versions[index] = replace(version, is_current=False, valid_to=valid_to)
                return


class FakeLoadRepository(LoadRepository):
    def __init__(self) -> None:
        self._loads: dict[int, Load] = {}
        self._next_id = 1

    def create(self, load: Load) -> Load:
        stored = replace(load, id=self._next_id)
        self._loads[self._next_id] = stored
        self._next_id += 1
        return stored

    def get(self, load_id: int) -> Load | None:
        return self._loads.get(load_id)

    def mark_finished(self, load_id: int, accepted: int, rejected: int) -> Load:
        current = self._loads[load_id]
        updated = replace(
            current, accepted=accepted, rejected=rejected, finished_at=datetime.now(UTC)
        )
        self._loads[load_id] = updated
        return updated


class FakeRejectedRecordRepository(RejectedRecordRepository):
    def __init__(self) -> None:
        self._records: list[RejectedRecord] = []
        self._next_id = 1

    def add(self, record: RejectedRecord) -> RejectedRecord:
        stored = replace(record, id=self._next_id)
        self._next_id += 1
        self._records.append(stored)
        return stored

    def list_for_load(self, load_id: int) -> list[RejectedRecord]:
        return [r for r in self._records if r.load_id == load_id]


class FakeSession:
    def __init__(self) -> None:
        self.commit_count = 0

    def commit(self) -> None:
        self.commit_count += 1


@dataclass
class Harness:
    use_case: IngestBatch
    department_repo: FakeDepartmentRepository
    job_repo: FakeJobRepository
    employee_repo: FakeEmployeeRepository
    employee_version_repo: FakeEmployeeVersionRepository
    load_repo: FakeLoadRepository
    rejected_record_repo: FakeRejectedRecordRepository
    session: FakeSession


def make_harness(
    department_ids: set[int] | None = None,
    job_ids: set[int] | None = None,
    existing_employee: Employee | None = None,
    existing_version: EmployeeVersion | None = None,
) -> Harness:
    department_repo = FakeDepartmentRepository(
        {id_: Department(id=id_, name=f"Dept {id_}") for id_ in (department_ids or {1})}
    )
    job_repo = FakeJobRepository(
        {id_: Job(id=id_, name=f"Job {id_}") for id_ in (job_ids or {5})}
    )
    employee_repo = FakeEmployeeRepository()
    employee_version_repo = FakeEmployeeVersionRepository()
    if existing_employee is not None:
        employee_repo.add(existing_employee)
    if existing_version is not None:
        employee_version_repo.add(existing_version)
    load_repo = FakeLoadRepository()
    rejected_record_repo = FakeRejectedRecordRepository()
    session = FakeSession()
    use_case = IngestBatch(
        department_repo=department_repo,
        job_repo=job_repo,
        employee_repo=employee_repo,
        employee_version_repo=employee_version_repo,
        load_repo=load_repo,
        rejected_record_repo=rejected_record_repo,
        validation_service=ValidationService(department_repo=department_repo, job_repo=job_repo),
        session=session,  # type: ignore[arg-type]
    )
    return Harness(
        use_case=use_case,
        department_repo=department_repo,
        job_repo=job_repo,
        employee_repo=employee_repo,
        employee_version_repo=employee_version_repo,
        load_repo=load_repo,
        rejected_record_repo=rejected_record_repo,
        session=session,
    )


def make_department_row(**overrides: Any) -> dict[str, Any]:
    row: dict[str, Any] = {"id": 1, "department": "Engineering"}
    row.update(overrides)
    return row


def make_job_row(**overrides: Any) -> dict[str, Any]:
    row: dict[str, Any] = {"id": 5, "job": "Recruiter"}
    row.update(overrides)
    return row


def make_hire_row(**overrides: Any) -> dict[str, Any]:
    row: dict[str, Any] = {
        "id": 101,
        "name": "Ada Lovelace",
        "datetime": "2021-02-10T09:30:00Z",
        "department_id": 1,
        "job_id": 5,
    }
    row.update(overrides)
    return row


def make_existing_hire(
    employee_id: int = 101,
    name: str = "Ada Lovelace",
    department_id: int = 1,
    job_id: int = 5,
    hire_datetime: datetime = datetime(2021, 2, 10, 9, 30, tzinfo=UTC),
) -> tuple[Employee, EmployeeVersion]:
    employee = Employee(
        employee_id=employee_id,
        name_at_hire=name,
        hire_datetime=hire_datetime,
        hire_department_id=department_id,
        hire_job_id=job_id,
    )
    version = EmployeeVersion(
        employee_id=employee_id,
        name=name,
        department_id=department_id,
        job_id=job_id,
        valid_from=hire_datetime,
        valid_to=None,
        is_current=True,
    )
    return employee, version


def test_ingest_departments_all_valid_upserts_and_commits() -> None:
    harness = make_harness()
    rows = [
        make_department_row(id=1, department="Engineering"),
        make_department_row(id=2, department="Sales"),
        make_department_row(id=3, department="Marketing"),
    ]

    result = harness.use_case.ingest_departments(rows)

    assert result.accepted == 3
    assert result.rejected == 0
    assert result.rejected_rows == ()
    assert harness.session.commit_count == 1
    load = harness.load_repo.get(result.load_id)
    assert load is not None
    assert load.source == "api:departments"
    assert harness.department_repo.exists(2)


def test_ingest_departments_partial_success() -> None:
    harness = make_harness()
    rows = [
        make_department_row(id=1, department="Engineering"),
        make_department_row(id="bad", department="Sales"),
        make_department_row(id=3, department=""),
    ]

    result = harness.use_case.ingest_departments(rows)

    assert result.accepted == 1
    assert result.rejected == 2
    assert {r.row_index for r in result.rejected_rows} == {1, 2}


def test_ingest_jobs_all_valid_upserts_and_commits() -> None:
    harness = make_harness()
    rows = [make_job_row(id=5, job="Recruiter"), make_job_row(id=6, job="Engineer")]

    result = harness.use_case.ingest_jobs(rows)

    assert result.accepted == 2
    assert result.rejected == 0
    load = harness.load_repo.get(result.load_id)
    assert load is not None
    assert load.source == "api:jobs"


def test_ingest_hires_multi_defect_row_produces_multiple_rejected_rows_same_row_index() -> None:
    harness = make_harness(department_ids={1}, job_ids={5})
    rows = [make_hire_row(department_id=999, job_id=888)]

    result = harness.use_case.ingest_hires(rows)

    assert result.accepted == 0
    assert result.rejected == 1
    assert len(result.rejected_rows) == 2
    assert {r.row_index for r in result.rejected_rows} == {0}
    records = harness.rejected_record_repo.list_for_load(result.load_id)
    assert len(records) == 2
    assert all(r.raw_payload == rows[0] for r in records)
    assert all(r.load_id == result.load_id for r in records)


def test_ingest_hires_new_employee_creates_employee_and_initial_version() -> None:
    harness = make_harness(department_ids={1}, job_ids={5})
    row = make_hire_row()

    result = harness.use_case.ingest_hires([row])

    assert result.accepted == 1
    employee = harness.employee_repo.get(101)
    assert employee is not None
    assert employee.hire_datetime == datetime(2021, 2, 10, 9, 30, tzinfo=UTC)
    assert employee.hire_department_id == 1
    version = harness.employee_version_repo.get_current(101)
    assert version is not None
    assert version.is_current is True
    assert version.valid_from == employee.hire_datetime
    assert version.valid_to is None


def test_ingest_hires_identical_reupload_is_noop() -> None:
    employee, version = make_existing_hire()
    harness = make_harness(
        department_ids={1}, job_ids={5}, existing_employee=employee, existing_version=version
    )
    row = make_hire_row()

    result = harness.use_case.ingest_hires([row])

    assert result.accepted == 1
    assert result.rejected == 0
    assert harness.employee_version_repo.close_current_calls == []
    assert len(harness.employee_repo.add_calls) == 1
    assert len(harness.employee_version_repo.list_for_employee(101)) == 1


def test_ingest_hires_changed_reupload_closes_and_opens_version() -> None:
    employee, version = make_existing_hire(department_id=1)
    harness = make_harness(
        department_ids={1, 2},
        job_ids={5},
        existing_employee=employee,
        existing_version=version,
    )
    row = make_hire_row(department_id=2)

    result = harness.use_case.ingest_hires([row])

    assert result.accepted == 1
    assert harness.employee_version_repo.close_current_calls == [101]
    versions = harness.employee_version_repo.list_for_employee(101)
    assert len(versions) == 2
    old_version = next(v for v in versions if not v.is_current)
    new_version = next(v for v in versions if v.is_current)
    assert old_version.valid_to is not None
    assert new_version.department_id == 2
    assert new_version.valid_to is None
    # Hire facts are immutable: the employees row is never touched on a re-upload.
    stored_employee = harness.employee_repo.get(101)
    assert stored_employee is not None
    assert stored_employee.hire_department_id == 1
    assert stored_employee.hire_datetime == employee.hire_datetime
    assert len(harness.employee_repo.add_calls) == 1


def test_ingest_hires_duplicate_id_within_one_batch_new_then_changed() -> None:
    harness = make_harness(department_ids={1, 2}, job_ids={5})
    rows = [make_hire_row(department_id=1), make_hire_row(department_id=2)]

    result = harness.use_case.ingest_hires(rows)

    assert result.accepted == 2
    assert result.rejected == 0
    assert harness.employee_version_repo.close_current_calls == [101]
    versions = harness.employee_version_repo.list_for_employee(101)
    assert len(versions) == 2
    assert len(harness.employee_repo.add_calls) == 1


def test_ingest_hires_duplicate_id_within_one_batch_identical_twice() -> None:
    harness = make_harness(department_ids={1}, job_ids={5})
    row = make_hire_row()

    result = harness.use_case.ingest_hires([row, dict(row)])

    assert result.accepted == 2
    assert result.rejected == 0
    assert harness.employee_version_repo.close_current_calls == []
    assert len(harness.employee_version_repo.list_for_employee(101)) == 1
    assert len(harness.employee_repo.add_calls) == 1


def test_ingest_load_marked_finished_with_final_counts() -> None:
    harness = make_harness()
    rows = [make_department_row(id=1), make_department_row(id="bad")]

    result = harness.use_case.ingest_departments(rows)

    load = harness.load_repo.get(result.load_id)
    assert load is not None
    assert load.accepted == result.accepted == 1
    assert load.rejected == result.rejected == 1
    assert load.finished_at is not None


def test_ingest_all_rejected_records_share_one_load_id() -> None:
    harness = make_harness(department_ids={1}, job_ids={5})
    rows = [
        make_hire_row(id=1, department_id=999),
        make_hire_row(id=2, job_id=888),
        make_hire_row(id=3, name=""),
    ]

    result = harness.use_case.ingest_hires(rows)

    records = harness.rejected_record_repo.list_for_load(result.load_id)
    assert len(records) == 3
    assert all(r.load_id == result.load_id for r in records)
