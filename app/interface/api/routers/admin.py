"""POST /admin/backup/{table} and POST /admin/restore/{table}.

Admin endpoints for the AVRO backup/restore commands (docs/API_CONTRACT.md,
docs/BACKUP_RESTORE.md). They exist so the Streamlit "Backup & Restore" tab has something to
call; the `python -m app.application.backup/restore <table>` CLI commands still work
unchanged for direct operator use. This reverses the project's earlier "not HTTP endpoints"
decision — see docs/DECISIONS.md for why, and for the explicit caveat that these routes have
no authentication (this project has no user/role access control at all) and restore is
destructive: deployments must restrict `/admin/*` at the network/reverse-proxy level.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

import app.application.backup as backup_module
import app.application.restore as restore_module
from app.application.backup import Backup
from app.application.restore import Restore
from app.infrastructure.avro.tables import validate_table_name
from app.infrastructure.db.repositories import (
    SqlAlchemyDepartmentRepository,
    SqlAlchemyEmployeeRepository,
    SqlAlchemyEmployeeVersionRepository,
    SqlAlchemyJobRepository,
    SqlAlchemyLoadRepository,
    SqlAlchemyRejectedRecordRepository,
)
from app.interface.api.dependencies import get_db
from app.interface.api.schemas import BackupOut, RestoreOut

router = APIRouter(prefix="/admin", tags=["admin"])


def _error(status_code: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"error": {"code": code, "message": message, "detail": None}},
    )


def _build_backup(session: Session) -> Backup:
    # data_dir is looked up on the module at call time (not baked into a default parameter
    # at import time) so tests can monkeypatch backup_module.DEFAULT_DATA_DIR.
    return Backup(
        department_repo=SqlAlchemyDepartmentRepository(session),
        job_repo=SqlAlchemyJobRepository(session),
        employee_repo=SqlAlchemyEmployeeRepository(session),
        employee_version_repo=SqlAlchemyEmployeeVersionRepository(session),
        load_repo=SqlAlchemyLoadRepository(session),
        rejected_record_repo=SqlAlchemyRejectedRecordRepository(session),
        data_dir=backup_module.DEFAULT_DATA_DIR,
    )


def _build_restore(session: Session) -> Restore:
    return Restore(
        department_repo=SqlAlchemyDepartmentRepository(session),
        job_repo=SqlAlchemyJobRepository(session),
        employee_repo=SqlAlchemyEmployeeRepository(session),
        employee_version_repo=SqlAlchemyEmployeeVersionRepository(session),
        load_repo=SqlAlchemyLoadRepository(session),
        rejected_record_repo=SqlAlchemyRejectedRecordRepository(session),
        session=session,
        data_dir=restore_module.DEFAULT_DATA_DIR,
    )


@router.post("/backup/{table}", response_model=BackupOut)
def backup_table(table: str, session: Session = Depends(get_db)) -> BackupOut | JSONResponse:
    try:
        validate_table_name(table)
    except ValueError:
        return _error(404, "UNKNOWN_TABLE", f"unknown table {table!r}")
    path = _build_backup(session).run(table)
    return BackupOut(table=table, path=str(path))


@router.post("/restore/{table}", response_model=RestoreOut)
def restore_table(table: str, session: Session = Depends(get_db)) -> RestoreOut | JSONResponse:
    try:
        validate_table_name(table)
    except ValueError:
        return _error(404, "UNKNOWN_TABLE", f"unknown table {table!r}")
    try:
        restored = _build_restore(session).run(table)
    except FileNotFoundError:
        return _error(404, "BACKUP_NOT_FOUND", f"no backup file found for {table!r}")
    return RestoreOut(table=table, restored=restored)
