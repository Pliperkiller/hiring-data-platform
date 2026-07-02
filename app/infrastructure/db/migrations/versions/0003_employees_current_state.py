"""employees current state

Revision ID: 0003_employees_current_state
Revises: 0002_report_materialized_views
Create Date: 2026-07-02 12:00:00.000000

Adds name/department_id/job_id to employees, tracking the employee's CURRENT state
(kept in sync with employee_versions on every SCD transition), alongside the existing
immutable hire facts (name_at_hire/hire_department_id/hire_job_id). See docs/DECISIONS.md
for why: employees previously held only the hire fact, with no way to read an employee's
current status without joining to employee_versions.

Existing rows are backfilled from their hire facts (correct: at first load, current ==
hire), then the columns are set NOT NULL.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0003_employees_current_state"
down_revision: str | Sequence[str] | None = "0002_report_materialized_views"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("employees", sa.Column("name", sa.Text(), nullable=True))
    op.add_column("employees", sa.Column("department_id", sa.Integer(), nullable=True))
    op.add_column("employees", sa.Column("job_id", sa.Integer(), nullable=True))

    op.execute(
        "UPDATE employees SET name = name_at_hire, department_id = hire_department_id, "
        "job_id = hire_job_id"
    )

    op.alter_column("employees", "name", nullable=False)
    op.alter_column("employees", "department_id", nullable=False)
    op.alter_column("employees", "job_id", nullable=False)

    op.create_foreign_key(
        "fk_employees_department_id", "employees", "departments", ["department_id"], ["id"]
    )
    op.create_foreign_key("fk_employees_job_id", "employees", "jobs", ["job_id"], ["id"])


def downgrade() -> None:
    op.drop_constraint("fk_employees_job_id", "employees", type_="foreignkey")
    op.drop_constraint("fk_employees_department_id", "employees", type_="foreignkey")
    op.drop_column("employees", "job_id")
    op.drop_column("employees", "department_id")
    op.drop_column("employees", "name")
