"""POST /admin/backup/{table}, POST /admin/restore/{table}, and POST /admin/reset.

Admin endpoints for the AVRO backup/restore commands (docs/API_CONTRACT.md,
docs/BACKUP_RESTORE.md) plus the full-database reset used by the Streamlit Admin tab's
typed-confirmation control. They exist so the Streamlit Admin tab has something to call; the
`python -m app.application.backup/restore <table>` CLI commands still work unchanged for direct
operator use (reset has no CLI entry point — it is deliberately only reachable through this
endpoint or the password-gated UI). This reverses the project's earlier "not HTTP endpoints"
decision — see docs/DECISIONS.md for why, and for the explicit caveat that these routes have
no authentication (this project has no user/role access control at all): restore and reset are
both destructive, and a production deployment should restrict `/admin/*` at the
network/reverse-proxy level — a restriction this phase evaluated and deliberately deferred (see
docs/DECISIONS.md); the Admin tab's password gate is a UI-layer mitigation only and does not
protect these routes from a direct HTTP request.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

import app.application.backup as backup_module
import app.application.restore as restore_module
from app.application.backup import Backup
from app.application.reset import Reset
from app.application.restore import Restore
from app.infrastructure.avro.tables import validate_table_name
from app.infrastructure.db.repositories import (
    SqlAlchemyDepartmentRepository,
    SqlAlchemyEmployeeRepository,
    SqlAlchemyEmployeeVersionRepository,
    SqlAlchemyJobRepository,
    SqlAlchemyLoadRepository,
    SqlAlchemyRejectedRecordRepository,
    SqlAlchemyReportRepository,
)
from app.interface.api.dependencies import get_db
from app.interface.api.schemas import BackupOut, ResetOut, RestoreOut

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


def _build_reset(session: Session) -> Reset:
    return Reset(
        department_repo=SqlAlchemyDepartmentRepository(session),
        job_repo=SqlAlchemyJobRepository(session),
        employee_repo=SqlAlchemyEmployeeRepository(session),
        employee_version_repo=SqlAlchemyEmployeeVersionRepository(session),
        load_repo=SqlAlchemyLoadRepository(session),
        rejected_record_repo=SqlAlchemyRejectedRecordRepository(session),
        report_repo=SqlAlchemyReportRepository(session),
        session=session,
    )


@router.post(
    "/backup/{table}",
    response_model=BackupOut,
    summary="Back up one table to AVRO",
    description=(
        "Writes `data/<table>.avro` from the current contents of `table`. Not reachable "
        "externally in a hardened deployment — see the module note on `/admin/*` above."
    ),
)
def backup_table(table: str, session: Session = Depends(get_db)) -> BackupOut | JSONResponse:
    try:
        validate_table_name(table)
    except ValueError:
        return _error(404, "UNKNOWN_TABLE", f"unknown table {table!r}")
    path = _build_backup(session).run(table)
    return BackupOut(table=table, path=str(path))


@router.post(
    "/restore/{table}",
    response_model=RestoreOut,
    summary="Restore one table from AVRO (full replace)",
    description=(
        "Truncates `table` and reloads it from `data/<table>.avro`. Destructive: this replaces "
        "the table's contents, it never merges. Not reachable externally in a hardened "
        "deployment — see the module note on `/admin/*` above."
    ),
)
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


@router.post(
    "/reset",
    response_model=ResetOut,
    summary="Truncate all tables and refresh reports",
    description=(
        "Truncates all six tables and refreshes both report views. The single most destructive "
        "operation in the app — it does not touch `data/*.avro`, so existing backups survive a "
        "reset untouched. Not reachable externally in a hardened deployment — see the module "
        "note on `/admin/*` above."
    ),
)
def reset_database(session: Session = Depends(get_db)) -> ResetOut:
    _build_reset(session).run()
    return ResetOut()
