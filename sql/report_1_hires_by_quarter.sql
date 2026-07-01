-- ============================================================
-- Report 1: Hires by department and job, per quarter (2021)
-- ============================================================
-- Counts each employee once, by the quarter of their hire date, grouped by
-- their hire-time department and job (not the current ones).
--
-- Decisions applied:
--   - Year 2021 only (excludes the 2022 records present in the data).
--   - Valid records only: guaranteed by construction, since invalid rows
--     never enter the employees table.
--   - Pivot to Q1..Q4 columns via conditional count (SUM CASE): portable and
--     readable, no dependency on the proprietary PIVOT operator.
--   - Only combinations with at least one hire in the year are shown: this
--     falls out of GROUP BY (a combo with no rows does not appear). Zeros
--     within a shown row do appear, matching the challenge example.
--
-- Timezone note: EXTRACT(QUARTER/YEAR) over a timestamptz uses the session
-- timezone. The database must run in UTC so quarters are deterministic.
--
-- Materialized as a view; refresh at the end of each load.
-- ============================================================

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

-- Refresh after each load:
--   REFRESH MATERIALIZED VIEW report_hires_by_quarter;

-- Verified against the source CSVs:
--   933 combinations with at least one hire; sum of Q1..Q4 = 1643 (total
--   valid 2021 hires).
