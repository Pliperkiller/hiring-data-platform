"""Read-only report row entities, sourced from the materialized views in sql/.

These carry no business rules; they exist as typed rows matching the report_hires_by_quarter
and report_departments_above_average view columns, kept as dataclasses for consistency with
every other domain entity in this codebase.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class HireByQuarterRow:
    department: str
    job: str
    q1: int
    q2: int
    q3: int
    q4: int


@dataclass(frozen=True, slots=True)
class DepartmentAboveAverageRow:
    id: int
    department: str
    hired: int
