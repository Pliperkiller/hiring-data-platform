"""Single source of truth for the six backup/restore table names and their restore order.

See docs/BACKUP_RESTORE.md: departments/jobs, then employees, then employee_versions/loads,
then rejected_records. Backup and restore CLIs are strictly single-table (docs/DECISIONS.md),
so this order matters only as an operational sequence an operator follows across invocations,
not as internal orchestration logic.
"""

from __future__ import annotations

TABLE_NAMES: tuple[str, ...] = (
    "departments",
    "jobs",
    "employees",
    "employee_versions",
    "loads",
    "rejected_records",
)


def validate_table_name(table: str) -> None:
    if table not in TABLE_NAMES:
        raise ValueError(f"unknown table {table!r}; expected one of {', '.join(TABLE_NAMES)}")
