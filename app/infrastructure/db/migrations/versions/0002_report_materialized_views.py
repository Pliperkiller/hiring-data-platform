"""report materialized views

Revision ID: 0002_report_materialized_views
Revises: 0001_initial_schema
Create Date: 2026-07-02 05:30:00.000000

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0002_report_materialized_views"
down_revision: str | Sequence[str] | None = "0001_initial_schema"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Verified SQL from sql/report_1_hires_by_quarter.sql and
# sql/report_2_departments_above_average.sql — used as-is, not rederived.
REPORT_1_SQL = """
CREATE MATERIALIZED VIEW report_hires_by_quarter AS
SELECT
    d.department,
    j.job,
    SUM(CASE WHEN EXTRACT(QUARTER FROM e.hire_datetime) = 1 THEN 1 ELSE 0 END) AS "Q1",
    SUM(CASE WHEN EXTRACT(QUARTER FROM e.hire_datetime) = 2 THEN 1 ELSE 0 END) AS "Q2",
    SUM(CASE WHEN EXTRACT(QUARTER FROM e.hire_datetime) = 3 THEN 1 ELSE 0 END) AS "Q3",
    SUM(CASE WHEN EXTRACT(QUARTER FROM e.hire_datetime) = 4 THEN 1 ELSE 0 END) AS "Q4"
FROM employees e
JOIN departments d ON d.id = e.hire_department_id
JOIN jobs        j ON j.id = e.hire_job_id
WHERE EXTRACT(YEAR FROM e.hire_datetime) = 2021
GROUP BY d.department, j.job
ORDER BY d.department, j.job;
"""

REPORT_2_SQL = """
CREATE MATERIALIZED VIEW report_departments_above_average AS
WITH hires_2021 AS (
    SELECT e.hire_department_id AS dept_id, COUNT(*) AS hired
    FROM employees e
    WHERE EXTRACT(YEAR FROM e.hire_datetime) = 2021
    GROUP BY e.hire_department_id
)
SELECT h.dept_id AS id, d.department, h.hired
FROM hires_2021 h
JOIN departments d ON d.id = h.dept_id
WHERE h.hired > (SELECT AVG(hired) FROM hires_2021)
ORDER BY h.hired DESC;
"""


def upgrade() -> None:
    op.execute(REPORT_1_SQL)
    op.execute(REPORT_2_SQL)


def downgrade() -> None:
    op.execute("DROP MATERIALIZED VIEW IF EXISTS report_departments_above_average")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS report_hires_by_quarter")
