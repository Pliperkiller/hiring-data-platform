"""Restore use case: full replace of one table from data/<table>.avro.

Admin operation (also reachable via `POST /admin/restore/{table}` -- see docs/DECISIONS.md
for why that HTTP path exists despite restore being destructive). No re-validation -- see
docs/BACKUP_RESTORE.md ("a backup is trusted, already-clean data"). Wiring and CLI/HTTP
entrypoints live in app/interface/ -- see app/interface/composition.py and
app/interface/cli/restore.py.
"""

from __future__ import annotations

from pathlib import Path

from sqlalchemy.orm import Session

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


class Restore:
    def __init__(
        self,
        department_repo: DepartmentRepository,
        job_repo: JobRepository,
        employee_repo: EmployeeRepository,
        employee_version_repo: EmployeeVersionRepository,
        load_repo: LoadRepository,
        rejected_record_repo: RejectedRecordRepository,
        session: Session,
        codec: BackupCodec,
        data_dir: Path = DEFAULT_DATA_DIR,
    ) -> None:
        self._department_repo = department_repo
        self._job_repo = job_repo
        self._employee_repo = employee_repo
        self._employee_version_repo = employee_version_repo
        self._load_repo = load_repo
        self._rejected_record_repo = rejected_record_repo
        self._session = session
        self._codec = codec
        self._data_dir = data_dir

    def run(self, table: str) -> int:
        validate_table_name(table)
        path = self._data_dir / f"{table}.avro"
        rows = self._codec.read(table, path)

        if table == "departments":
            self._department_repo.truncate()
            for dept in rows:
                self._department_repo.upsert(dept)
        elif table == "jobs":
            self._job_repo.truncate()
            for job in rows:
                self._job_repo.upsert(job)
        elif table == "employees":
            self._employee_repo.truncate()
            for emp in rows:
                self._employee_repo.add(emp)
        elif table == "employee_versions":
            self._employee_version_repo.truncate()
            self._employee_version_repo.restore_all(rows)
        elif table == "loads":
            self._load_repo.truncate()
            self._load_repo.restore_all(rows)
        else:
            self._rejected_record_repo.truncate()
            self._rejected_record_repo.restore_all(rows)

        self._session.commit()
        return len(rows)


__all__ = ["Restore"]
