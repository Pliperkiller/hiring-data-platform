"""initial schema

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-07-01 18:56:36.391782

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0001_initial_schema"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "departments",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("department", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "jobs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("job", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "loads",
        sa.Column("id", sa.Integer(), sa.Identity(always=True), nullable=False),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column(
            "started_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("finished_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("accepted", sa.Integer(), server_default="0", nullable=False),
        sa.Column("rejected", sa.Integer(), server_default="0", nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "employees",
        sa.Column("employee_id", sa.Integer(), nullable=False),
        sa.Column("name_at_hire", sa.Text(), nullable=False),
        sa.Column("hire_datetime", postgresql.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("hire_department_id", sa.Integer(), nullable=False),
        sa.Column("hire_job_id", sa.Integer(), nullable=False),
        sa.Column(
            "first_loaded_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["hire_department_id"], ["departments.id"]),
        sa.ForeignKeyConstraint(["hire_job_id"], ["jobs.id"]),
        sa.PrimaryKeyConstraint("employee_id"),
    )
    op.create_index("ix_employees_hire_datetime", "employees", ["hire_datetime"], unique=False)
    op.create_index(
        "ix_employees_hire_department_id", "employees", ["hire_department_id"], unique=False
    )
    op.create_index("ix_employees_hire_job_id", "employees", ["hire_job_id"], unique=False)
    op.create_table(
        "rejected_records",
        sa.Column("id", sa.Integer(), sa.Identity(always=True), nullable=False),
        sa.Column("target_table", sa.Text(), nullable=False),
        sa.Column("raw_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("field", sa.Text(), nullable=True),
        sa.Column("reason_code", sa.Text(), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("load_id", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["load_id"], ["loads.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_rejected_records_load_id", "rejected_records", ["load_id"], unique=False
    )
    op.create_index(
        "ix_rejected_records_reason_code", "rejected_records", ["reason_code"], unique=False
    )
    op.create_table(
        "employee_versions",
        sa.Column("version_id", sa.Integer(), sa.Identity(always=True), nullable=False),
        sa.Column("employee_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("department_id", sa.Integer(), nullable=False),
        sa.Column("job_id", sa.Integer(), nullable=False),
        sa.Column("valid_from", postgresql.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("valid_to", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("is_current", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(["department_id"], ["departments.id"]),
        sa.ForeignKeyConstraint(["employee_id"], ["employees.employee_id"]),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"]),
        sa.PrimaryKeyConstraint("version_id"),
    )
    op.create_index(
        "ix_employee_versions_employee_id", "employee_versions", ["employee_id"], unique=False
    )
    op.create_index(
        "ux_employee_versions_current",
        "employee_versions",
        ["employee_id"],
        unique=True,
        postgresql_where=sa.text("is_current IS true"),
    )


def downgrade() -> None:
    op.drop_index(
        "ux_employee_versions_current",
        table_name="employee_versions",
        postgresql_where=sa.text("is_current IS true"),
    )
    op.drop_index("ix_employee_versions_employee_id", table_name="employee_versions")
    op.drop_table("employee_versions")
    op.drop_index("ix_rejected_records_reason_code", table_name="rejected_records")
    op.drop_index("ix_rejected_records_load_id", table_name="rejected_records")
    op.drop_table("rejected_records")
    op.drop_index("ix_employees_hire_job_id", table_name="employees")
    op.drop_index("ix_employees_hire_department_id", table_name="employees")
    op.drop_index("ix_employees_hire_datetime", table_name="employees")
    op.drop_table("employees")
    op.drop_table("loads")
    op.drop_table("jobs")
    op.drop_table("departments")
