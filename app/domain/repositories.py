"""Repository interfaces (ABCs).

Framework-agnostic: no SQLAlchemy or Session references here, per DESIGN.md's DDD rule
that the domain knows nothing about the database. Covers only the CRUD verbs exercisable
this phase; ingestion-orchestration methods belong to feature/ingestion-api.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime

from app.domain.employee import Employee, EmployeeVersion
from app.domain.reference import Department, Job
from app.domain.rejected_record import Load, RejectedRecord
from app.domain.report import DepartmentAboveAverageRow, HireByQuarterRow


class DepartmentRepository(ABC):
    @abstractmethod
    def upsert(self, department: Department) -> Department: ...

    @abstractmethod
    def get(self, department_id: int) -> Department | None: ...

    @abstractmethod
    def list_all(self) -> list[Department]: ...

    @abstractmethod
    def exists(self, department_id: int) -> bool: ...


class JobRepository(ABC):
    @abstractmethod
    def upsert(self, job: Job) -> Job: ...

    @abstractmethod
    def get(self, job_id: int) -> Job | None: ...

    @abstractmethod
    def list_all(self) -> list[Job]: ...

    @abstractmethod
    def exists(self, job_id: int) -> bool: ...


class EmployeeRepository(ABC):
    @abstractmethod
    def add(self, employee: Employee) -> Employee: ...

    @abstractmethod
    def get(self, employee_id: int) -> Employee | None: ...

    @abstractmethod
    def exists(self, employee_id: int) -> bool: ...

    @abstractmethod
    def list_all(self) -> list[Employee]: ...


class EmployeeVersionRepository(ABC):
    @abstractmethod
    def add(self, version: EmployeeVersion) -> EmployeeVersion: ...

    @abstractmethod
    def get_current(self, employee_id: int) -> EmployeeVersion | None: ...

    @abstractmethod
    def list_for_employee(self, employee_id: int) -> list[EmployeeVersion]: ...

    @abstractmethod
    def close_current(self, employee_id: int, valid_to: datetime) -> None: ...


class LoadRepository(ABC):
    @abstractmethod
    def create(self, load: Load) -> Load: ...

    @abstractmethod
    def get(self, load_id: int) -> Load | None: ...

    @abstractmethod
    def mark_finished(self, load_id: int, accepted: int, rejected: int) -> Load: ...


class RejectedRecordRepository(ABC):
    @abstractmethod
    def add(self, record: RejectedRecord) -> RejectedRecord: ...

    @abstractmethod
    def list_for_load(self, load_id: int) -> list[RejectedRecord]: ...


class ReportRepository(ABC):
    @abstractmethod
    def refresh_views(self) -> None: ...

    @abstractmethod
    def list_hires_by_quarter(self) -> list[HireByQuarterRow]: ...

    @abstractmethod
    def list_departments_above_average(self) -> list[DepartmentAboveAverageRow]: ...
