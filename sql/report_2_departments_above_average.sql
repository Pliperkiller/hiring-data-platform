-- ============================================================
-- Report 2: Departments that hired above average (2021)
-- ============================================================
-- Lists departments whose 2021 hire count exceeds the average, output
-- id | department | hired, ordered by hired descending.
--
-- Decisions applied:
--   - Year 2021 only. The year filter lives in the CTE and applies to both
--     the count and the average (this is where a prior version failed: it
--     compared an all-time count against a 2021 average).
--   - The average is computed only over departments that hired in the period
--     (the CTE is already filtered by GROUP BY). Avoids dormant departments
--     dragging the baseline down. With the current data all 12 departments
--     hired, so this equals the average over all departments.
--   - Attribution by hire-time department.
--
-- Materialized as a view; refresh at the end of each load.
-- ============================================================

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

-- Refresh after each load:
--   REFRESH MATERIALIZED VIEW report_departments_above_average;

-- Verified against the source CSVs:
--   Average 136.92; 7 departments above it:
--   Support 216, Engineering 205, Human Resources 201, Services 200,
--   Business Development 185, Research and Development 148, Marketing 142.
