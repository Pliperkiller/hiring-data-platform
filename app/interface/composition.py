"""Composition root for backup/restore: the one place that wires concrete infrastructure
(SQLAlchemy repositories, AvroBackupCodec) into the Backup/Restore use cases. Both the admin
router and the CLI entrypoints (app/interface/cli/) build their use cases through here instead
of each holding their own copy of the wiring.
"""

from __future__ import annotations

from pathlib import Path

from sqlalchemy.orm import Session

import app.application.backup as backup_module
import app.application.restore as restore_module
from app.application.backup import Backup
from app.application.restore import Restore
from app.infrastructure.avro.avro_backup_codec import AvroBackupCodec
from app.infrastructure.db.repositories import (
    SqlAlchemyDepartmentRepository,
    SqlAlchemyEmployeeRepository,
    SqlAlchemyEmployeeVersionRepository,
    SqlAlchemyJobRepository,
    SqlAlchemyLoadRepository,
    SqlAlchemyRejectedRecordRepository,
)


def build_backup(session: Session, data_dir: Path | None = None) -> Backup:
    return Backup(
        department_repo=SqlAlchemyDepartmentRepository(session),
        job_repo=SqlAlchemyJobRepository(session),
        employee_repo=SqlAlchemyEmployeeRepository(session),
        employee_version_repo=SqlAlchemyEmployeeVersionRepository(session),
        load_repo=SqlAlchemyLoadRepository(session),
        rejected_record_repo=SqlAlchemyRejectedRecordRepository(session),
        codec=AvroBackupCodec(),
        data_dir=data_dir if data_dir is not None else backup_module.DEFAULT_DATA_DIR,
    )


def build_restore(session: Session, data_dir: Path | None = None) -> Restore:
    return Restore(
        department_repo=SqlAlchemyDepartmentRepository(session),
        job_repo=SqlAlchemyJobRepository(session),
        employee_repo=SqlAlchemyEmployeeRepository(session),
        employee_version_repo=SqlAlchemyEmployeeVersionRepository(session),
        load_repo=SqlAlchemyLoadRepository(session),
        rejected_record_repo=SqlAlchemyRejectedRecordRepository(session),
        session=session,
        codec=AvroBackupCodec(),
        data_dir=data_dir if data_dir is not None else restore_module.DEFAULT_DATA_DIR,
    )


__all__ = ["build_backup", "build_restore"]
