"""SQLAlchemy declarative models for all tables in docs/DATA_MODEL.md."""

from datetime import datetime

from sqlalchemy import ForeignKey, Identity, Index, Text
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.sql import func


class Base(DeclarativeBase):
    type_annotation_map = {str: Text}


class DepartmentModel(Base):
    __tablename__ = "departments"

    id: Mapped[int] = mapped_column(primary_key=True)
    department: Mapped[str] = mapped_column(nullable=False)


class JobModel(Base):
    __tablename__ = "jobs"

    id: Mapped[int] = mapped_column(primary_key=True)
    job: Mapped[str] = mapped_column(nullable=False)


class EmployeeModel(Base):
    """Hire facts: one row per employee, immutable after first load."""

    __tablename__ = "employees"

    employee_id: Mapped[int] = mapped_column(primary_key=True)
    name_at_hire: Mapped[str] = mapped_column(nullable=False)
    hire_datetime: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    hire_department_id: Mapped[int] = mapped_column(
        ForeignKey("departments.id"), nullable=False
    )
    hire_job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id"), nullable=False)
    first_loaded_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )

    versions: Mapped[list["EmployeeVersionModel"]] = relationship(
        back_populates="employee", order_by="EmployeeVersionModel.valid_from"
    )

    __table_args__ = (
        Index("ix_employees_hire_department_id", "hire_department_id"),
        Index("ix_employees_hire_job_id", "hire_job_id"),
        Index("ix_employees_hire_datetime", "hire_datetime"),
    )


class EmployeeVersionModel(Base):
    """SCD Type 2: changing attributes over time."""

    __tablename__ = "employee_versions"

    version_id: Mapped[int] = mapped_column(Identity(always=True), primary_key=True)
    employee_id: Mapped[int] = mapped_column(
        ForeignKey("employees.employee_id"), nullable=False
    )
    name: Mapped[str] = mapped_column(nullable=False)
    department_id: Mapped[int] = mapped_column(ForeignKey("departments.id"), nullable=False)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id"), nullable=False)
    valid_from: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    valid_to: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    is_current: Mapped[bool] = mapped_column(nullable=False)

    employee: Mapped["EmployeeModel"] = relationship(back_populates="versions")

    __table_args__ = (
        Index("ix_employee_versions_employee_id", "employee_id"),
        Index(
            "ux_employee_versions_current",
            "employee_id",
            unique=True,
            postgresql_where=is_current.is_(True),
        ),
    )


class LoadModel(Base):
    __tablename__ = "loads"

    id: Mapped[int] = mapped_column(Identity(always=True), primary_key=True)
    source: Mapped[str] = mapped_column(nullable=False)
    started_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    finished_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    accepted: Mapped[int] = mapped_column(nullable=False, server_default="0")
    rejected: Mapped[int] = mapped_column(nullable=False, server_default="0")


class RejectedRecordModel(Base):
    __tablename__ = "rejected_records"

    id: Mapped[int] = mapped_column(Identity(always=True), primary_key=True)
    target_table: Mapped[str] = mapped_column(nullable=False)
    raw_payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    field: Mapped[str | None] = mapped_column(nullable=True)
    reason_code: Mapped[str] = mapped_column(nullable=False)
    message: Mapped[str] = mapped_column(nullable=False)
    load_id: Mapped[int | None] = mapped_column(ForeignKey("loads.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        Index("ix_rejected_records_reason_code", "reason_code"),
        Index("ix_rejected_records_load_id", "load_id"),
    )


class ReportHiresByQuarterModel(Base):
    """Read-only mapping onto the report_hires_by_quarter materialized view."""

    __tablename__ = "report_hires_by_quarter"

    department: Mapped[str] = mapped_column(primary_key=True)
    job: Mapped[str] = mapped_column(primary_key=True)
    Q1: Mapped[int] = mapped_column()
    Q2: Mapped[int] = mapped_column()
    Q3: Mapped[int] = mapped_column()
    Q4: Mapped[int] = mapped_column()


class ReportDepartmentAboveAverageModel(Base):
    """Read-only mapping onto the report_departments_above_average materialized view."""

    __tablename__ = "report_departments_above_average"

    id: Mapped[int] = mapped_column(primary_key=True)
    department: Mapped[str] = mapped_column()
    hired: Mapped[int] = mapped_column()
