"""Concrete SQLAlchemy repository implementations.

Each method flushes but does not commit: the caller (a test fixture today, a use case in
later phases) owns the transaction boundary.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.sql import func

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
from app.domain.value_objects import ReasonCode
from app.infrastructure.db.models import (
    DepartmentModel,
    EmployeeModel,
    EmployeeVersionModel,
    JobModel,
    LoadModel,
    RejectedRecordModel,
)


class SqlAlchemyDepartmentRepository(DepartmentRepository):
    def __init__(self, session: Session) -> None:
        self._session = session

    def upsert(self, department: Department) -> Department:
        model = self._session.get(DepartmentModel, department.id)
        if model is None:
            model = DepartmentModel(id=department.id, department=department.name)
            self._session.add(model)
        else:
            model.department = department.name
        self._session.flush()
        return Department(id=model.id, name=model.department)

    def get(self, department_id: int) -> Department | None:
        model = self._session.get(DepartmentModel, department_id)
        return Department(id=model.id, name=model.department) if model else None

    def list_all(self) -> list[Department]:
        rows = self._session.scalars(select(DepartmentModel).order_by(DepartmentModel.id))
        return [Department(id=r.id, name=r.department) for r in rows]

    def exists(self, department_id: int) -> bool:
        return self._session.get(DepartmentModel, department_id) is not None


class SqlAlchemyJobRepository(JobRepository):
    def __init__(self, session: Session) -> None:
        self._session = session

    def upsert(self, job: Job) -> Job:
        model = self._session.get(JobModel, job.id)
        if model is None:
            model = JobModel(id=job.id, job=job.name)
            self._session.add(model)
        else:
            model.job = job.name
        self._session.flush()
        return Job(id=model.id, name=model.job)

    def get(self, job_id: int) -> Job | None:
        model = self._session.get(JobModel, job_id)
        return Job(id=model.id, name=model.job) if model else None

    def list_all(self) -> list[Job]:
        rows = self._session.scalars(select(JobModel).order_by(JobModel.id))
        return [Job(id=r.id, name=r.job) for r in rows]

    def exists(self, job_id: int) -> bool:
        return self._session.get(JobModel, job_id) is not None


class SqlAlchemyEmployeeRepository(EmployeeRepository):
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, employee: Employee) -> Employee:
        model = EmployeeModel(
            employee_id=employee.employee_id,
            name_at_hire=employee.name_at_hire,
            hire_datetime=employee.hire_datetime,
            hire_department_id=employee.hire_department_id,
            hire_job_id=employee.hire_job_id,
        )
        self._session.add(model)
        self._session.flush()
        return self._to_domain(model)

    def get(self, employee_id: int) -> Employee | None:
        model = self._session.get(EmployeeModel, employee_id)
        return self._to_domain(model) if model else None

    def exists(self, employee_id: int) -> bool:
        return self._session.get(EmployeeModel, employee_id) is not None

    def list_all(self) -> list[Employee]:
        rows = self._session.scalars(select(EmployeeModel).order_by(EmployeeModel.employee_id))
        return [self._to_domain(r) for r in rows]

    @staticmethod
    def _to_domain(model: EmployeeModel) -> Employee:
        return Employee(
            employee_id=model.employee_id,
            name_at_hire=model.name_at_hire,
            hire_datetime=model.hire_datetime,
            hire_department_id=model.hire_department_id,
            hire_job_id=model.hire_job_id,
            first_loaded_at=model.first_loaded_at,
        )


class SqlAlchemyEmployeeVersionRepository(EmployeeVersionRepository):
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, version: EmployeeVersion) -> EmployeeVersion:
        model = EmployeeVersionModel(
            employee_id=version.employee_id,
            name=version.name,
            department_id=version.department_id,
            job_id=version.job_id,
            valid_from=version.valid_from,
            valid_to=version.valid_to,
            is_current=version.is_current,
        )
        self._session.add(model)
        self._session.flush()
        return self._to_domain(model)

    def get_current(self, employee_id: int) -> EmployeeVersion | None:
        model = self._session.scalar(
            select(EmployeeVersionModel).where(
                EmployeeVersionModel.employee_id == employee_id,
                EmployeeVersionModel.is_current.is_(True),
            )
        )
        return self._to_domain(model) if model else None

    def list_for_employee(self, employee_id: int) -> list[EmployeeVersion]:
        rows = self._session.scalars(
            select(EmployeeVersionModel)
            .where(EmployeeVersionModel.employee_id == employee_id)
            .order_by(EmployeeVersionModel.valid_from)
        )
        return [self._to_domain(r) for r in rows]

    def close_current(self, employee_id: int, valid_to: datetime) -> None:
        current = self._session.scalar(
            select(EmployeeVersionModel).where(
                EmployeeVersionModel.employee_id == employee_id,
                EmployeeVersionModel.is_current.is_(True),
            )
        )
        if current is not None:
            current.is_current = False
            current.valid_to = valid_to
            self._session.flush()

    @staticmethod
    def _to_domain(model: EmployeeVersionModel) -> EmployeeVersion:
        return EmployeeVersion(
            employee_id=model.employee_id,
            name=model.name,
            department_id=model.department_id,
            job_id=model.job_id,
            valid_from=model.valid_from,
            valid_to=model.valid_to,
            is_current=model.is_current,
            version_id=model.version_id,
        )


class SqlAlchemyLoadRepository(LoadRepository):
    def __init__(self, session: Session) -> None:
        self._session = session

    def create(self, load: Load) -> Load:
        model = LoadModel(source=load.source)
        self._session.add(model)
        self._session.flush()
        return self._to_domain(model)

    def get(self, load_id: int) -> Load | None:
        model = self._session.get(LoadModel, load_id)
        return self._to_domain(model) if model else None

    def mark_finished(self, load_id: int, accepted: int, rejected: int) -> Load:
        model = self._session.get(LoadModel, load_id)
        if model is None:
            raise ValueError(f"Load {load_id} not found")
        model.finished_at = func.now()
        model.accepted = accepted
        model.rejected = rejected
        self._session.flush()
        self._session.refresh(model)
        return self._to_domain(model)

    @staticmethod
    def _to_domain(model: LoadModel) -> Load:
        return Load(
            id=model.id,
            source=model.source,
            started_at=model.started_at,
            finished_at=model.finished_at,
            accepted=model.accepted,
            rejected=model.rejected,
        )


class SqlAlchemyRejectedRecordRepository(RejectedRecordRepository):
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, record: RejectedRecord) -> RejectedRecord:
        model = RejectedRecordModel(
            target_table=record.target_table,
            raw_payload=record.raw_payload,
            field=record.field,
            reason_code=record.reason_code,
            message=record.message,
            load_id=record.load_id,
        )
        self._session.add(model)
        self._session.flush()
        return self._to_domain(model)

    def list_for_load(self, load_id: int) -> list[RejectedRecord]:
        rows = self._session.scalars(
            select(RejectedRecordModel).where(RejectedRecordModel.load_id == load_id)
        )
        return [self._to_domain(r) for r in rows]

    @staticmethod
    def _to_domain(model: RejectedRecordModel) -> RejectedRecord:
        return RejectedRecord(
            id=model.id,
            target_table=model.target_table,
            raw_payload=model.raw_payload,
            field=model.field,
            reason_code=ReasonCode(model.reason_code),
            message=model.message,
            load_id=model.load_id,
            created_at=model.created_at,
        )
