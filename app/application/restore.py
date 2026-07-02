"""Restore use case: full replace of one table from data/<table>.avro.

Admin operation (CLI: `python -m app.application.restore <table>`; also reachable via the
`POST /admin/restore/{table}` endpoint used by the Streamlit "Backup & Restore" tab — see
docs/DECISIONS.md for why that HTTP path exists despite restore being destructive). No
re-validation — see docs/BACKUP_RESTORE.md ("a backup is trusted, already-clean data").
"""

from __future__ import annotations

import sys
from pathlib import Path

from sqlalchemy.orm import Session

from app.domain.repositories import (
    DepartmentRepository,
    EmployeeRepository,
    EmployeeVersionRepository,
    JobRepository,
    LoadRepository,
    RejectedRecordRepository,
)
from app.infrastructure.avro.codec import from_avro_dicts, read_avro
from app.infrastructure.avro.tables import TABLE_NAMES, validate_table_name

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
        data_dir: Path = DEFAULT_DATA_DIR,
    ) -> None:
        self._department_repo = department_repo
        self._job_repo = job_repo
        self._employee_repo = employee_repo
        self._employee_version_repo = employee_version_repo
        self._load_repo = load_repo
        self._rejected_record_repo = rejected_record_repo
        self._session = session
        self._data_dir = data_dir

    def run(self, table: str) -> int:
        validate_table_name(table)
        path = self._data_dir / f"{table}.avro"
        rows = from_avro_dicts(table, read_avro(path))

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


def _build_restore(session: Session, data_dir: Path = DEFAULT_DATA_DIR) -> Restore:
    from app.infrastructure.db.repositories import (
        SqlAlchemyDepartmentRepository,
        SqlAlchemyEmployeeRepository,
        SqlAlchemyEmployeeVersionRepository,
        SqlAlchemyJobRepository,
        SqlAlchemyLoadRepository,
        SqlAlchemyRejectedRecordRepository,
    )

    return Restore(
        department_repo=SqlAlchemyDepartmentRepository(session),
        job_repo=SqlAlchemyJobRepository(session),
        employee_repo=SqlAlchemyEmployeeRepository(session),
        employee_version_repo=SqlAlchemyEmployeeVersionRepository(session),
        load_repo=SqlAlchemyLoadRepository(session),
        rejected_record_repo=SqlAlchemyRejectedRecordRepository(session),
        session=session,
        data_dir=data_dir,
    )


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(
            f"usage: python -m app.application.restore <table>\n"
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
        count = _build_restore(session).run(table)
        print(f"restored {table}: {count} row(s)")
        return 0
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))


__all__ = ["Restore"]
