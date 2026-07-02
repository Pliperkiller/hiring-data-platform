"""Backup use case: export one table to data/<table>.avro.

Admin operation. Wiring (concrete repositories, codec) and CLI/HTTP entrypoints live in
app/interface/ -- see app/interface/composition.py and app/interface/cli/backup.py.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.domain.backup_codec import BackupCodec, validate_table_name
from app.domain.repositories import (
    DepartmentRepository,
    EmployeeRepository,
    EmployeeVersionRepository,
    JobRepository,
    LoadRepository,
    RejectedRecordRepository,
)

DEFAULT_DATA_DIR = Path("data")


class Backup:
    def __init__(
        self,
        department_repo: DepartmentRepository,
        job_repo: JobRepository,
        employee_repo: EmployeeRepository,
        employee_version_repo: EmployeeVersionRepository,
        load_repo: LoadRepository,
        rejected_record_repo: RejectedRecordRepository,
        codec: BackupCodec,
        data_dir: Path = DEFAULT_DATA_DIR,
    ) -> None:
        self._department_repo = department_repo
        self._job_repo = job_repo
        self._employee_repo = employee_repo
        self._employee_version_repo = employee_version_repo
        self._load_repo = load_repo
        self._rejected_record_repo = rejected_record_repo
        self._codec = codec
        self._data_dir = data_dir

    def run(self, table: str) -> Path:
        validate_table_name(table)
        rows: list[Any]
        if table == "departments":
            rows = self._department_repo.list_all()
        elif table == "jobs":
            rows = self._job_repo.list_all()
        elif table == "employees":
            rows = self._employee_repo.list_all()
        elif table == "employee_versions":
            rows = self._employee_version_repo.list_all()
        elif table == "loads":
            rows = self._load_repo.list_all()
        else:
            rows = self._rejected_record_repo.list_all()

        path = self._data_dir / f"{table}.avro"
        self._codec.write(table, rows, path)
        return path


__all__ = ["Backup"]
