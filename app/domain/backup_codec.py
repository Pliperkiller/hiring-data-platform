"""Backup/restore domain concerns: which tables are in scope, and the serialization port.

Kept out of `repositories.py` (which covers only the CRUD verbs on entity repositories) since
a codec's job -- converting domain entities to/from a portable file format -- is a distinct
outbound port from persistence, even though the application layer depends on both abstractly.

`TABLE_NAMES`/`validate_table_name` used to live in `app/infrastructure/avro/tables.py`, but
the six backup/restore table names are business data (which aggregates support backup), not an
AVRO detail, and `Backup`/`Restore` need to validate a table name without importing
infrastructure -- see docs/DECISIONS.md.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

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


class BackupCodec(ABC):
    @abstractmethod
    def write(self, table: str, rows: list[Any], path: Path) -> None: ...

    @abstractmethod
    def read(self, table: str, path: Path) -> list[Any]: ...
