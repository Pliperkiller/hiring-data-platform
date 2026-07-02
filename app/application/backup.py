"""Backup use case: export one table to data/<table>.avro.

Admin CLI, never HTTP — see docs/API_CONTRACT.md and docs/BACKUP_RESTORE.md. Invoked as
`python -m app.application.backup <table>`.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.domain.repositories import (
    DepartmentRepository,
    EmployeeRepository,
    EmployeeVersionRepository,
    JobRepository,
    LoadRepository,
    RejectedRecordRepository,
)
from app.infrastructure.avro.codec import to_avro_dicts, write_avro
from app.infrastructure.avro.tables import TABLE_NAMES, validate_table_name

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
        data_dir: Path = DEFAULT_DATA_DIR,
    ) -> None:
        self._department_repo = department_repo
        self._job_repo = job_repo
        self._employee_repo = employee_repo
        self._employee_version_repo = employee_version_repo
        self._load_repo = load_repo
        self._rejected_record_repo = rejected_record_repo
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

        avro_rows = to_avro_dicts(table, rows)
        path = self._data_dir / f"{table}.avro"
        write_avro(table, avro_rows, path)
        return path


def _build_backup(session: Session, data_dir: Path = DEFAULT_DATA_DIR) -> Backup:
    from app.infrastructure.db.repositories import (
        SqlAlchemyDepartmentRepository,
        SqlAlchemyEmployeeRepository,
        SqlAlchemyEmployeeVersionRepository,
        SqlAlchemyJobRepository,
        SqlAlchemyLoadRepository,
        SqlAlchemyRejectedRecordRepository,
    )

    return Backup(
        department_repo=SqlAlchemyDepartmentRepository(session),
        job_repo=SqlAlchemyJobRepository(session),
        employee_repo=SqlAlchemyEmployeeRepository(session),
        employee_version_repo=SqlAlchemyEmployeeVersionRepository(session),
        load_repo=SqlAlchemyLoadRepository(session),
        rejected_record_repo=SqlAlchemyRejectedRecordRepository(session),
        data_dir=data_dir,
    )


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(
            f"usage: python -m app.application.backup <table>\n"
            f"  tables: {', '.join(TABLE_NAMES)}",
            file=sys.stderr,
        )
        return 2
    table = argv[1]
    try:
        validate_table_name(table)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    from app.infrastructure.config import get_settings
    from app.infrastructure.db.session import build_engine, build_sessionmaker

    engine = build_engine(get_settings().database_url)
    session = build_sessionmaker(engine)()
    try:
        path = _build_backup(session).run(table)
        print(f"backed up {table} -> {path}")
        return 0
    finally:
        session.close()


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))


__all__ = ["Backup"]
