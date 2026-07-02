"""Integration tests for the Backup/Restore use cases against a real Postgres database.

Reuses the existing db_session fixture as-is: TRUNCATE is transactional in Postgres, so
seed -> backup -> wipe -> restore all execute through the same open connection/transaction
with no visibility gap, exactly like every other integration test in this suite (confirmed
via a throwaway check during planning; see docs/DECISIONS.md).
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.application.backup import Backup
from app.application.restore import Restore
from app.domain.employee import Employee, EmployeeVersion
from app.domain.reference import Department, Job
from app.domain.rejected_record import Load, RejectedRecord
from app.domain.value_objects import ReasonCode
from app.infrastructure.avro.tables import TABLE_NAMES
from app.infrastructure.db.repositories import (
    SqlAlchemyDepartmentRepository,
    SqlAlchemyEmployeeRepository,
    SqlAlchemyEmployeeVersionRepository,
    SqlAlchemyJobRepository,
    SqlAlchemyLoadRepository,
    SqlAlchemyRejectedRecordRepository,
)

pytestmark = pytest.mark.usefixtures("apply_migrations")

UTC_NOW = datetime(2021, 3, 15, 9, 30, tzinfo=UTC)


def _millis(dt: datetime) -> datetime:
    return dt.replace(microsecond=(dt.microsecond // 1000) * 1000)


def make_backup(session: Session, data_dir: Path) -> Backup:
    return Backup(
        department_repo=SqlAlchemyDepartmentRepository(session),
        job_repo=SqlAlchemyJobRepository(session),
        employee_repo=SqlAlchemyEmployeeRepository(session),
        employee_version_repo=SqlAlchemyEmployeeVersionRepository(session),
        load_repo=SqlAlchemyLoadRepository(session),
        rejected_record_repo=SqlAlchemyRejectedRecordRepository(session),
        data_dir=data_dir,
    )


def make_restore(session: Session, data_dir: Path) -> Restore:
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


def seed_full_dataset(session: Session) -> None:
    """Seed one FK-complete row per table, in dependency order."""
    SqlAlchemyDepartmentRepository(session).upsert(Department(id=1, name="Engineering"))
    SqlAlchemyJobRepository(session).upsert(Job(id=1, name="Recruiter"))
    SqlAlchemyEmployeeRepository(session).add(
        Employee(
            employee_id=1,
            name_at_hire="Alice",
            hire_datetime=UTC_NOW,
            hire_department_id=1,
            hire_job_id=1,
        )
    )
    SqlAlchemyEmployeeVersionRepository(session).add(
        EmployeeVersion(
            employee_id=1,
            name="Alice",
            department_id=1,
            job_id=1,
            valid_from=UTC_NOW,
            valid_to=None,
            is_current=True,
        )
    )
    load = SqlAlchemyLoadRepository(session).create(Load(source="historical"))
    assert load.id is not None
    SqlAlchemyRejectedRecordRepository(session).add(
        RejectedRecord(
            target_table="departments",
            raw_payload={"id": "x"},
            reason_code=ReasonCode.MISSING_ID,
            message="id is empty",
            field="id",
            load_id=load.id,
        )
    )


@pytest.mark.parametrize("table", TABLE_NAMES)
def test_backup_then_restore_round_trips_each_table(
    db_session: Session, tmp_path: Path, table: str
) -> None:
    seed_full_dataset(db_session)
    backup = make_backup(db_session, tmp_path)
    restore = make_restore(db_session, tmp_path)

    path = backup.run(table)
    assert path.exists()

    restore.run(table)

    if table == "departments":
        rows = SqlAlchemyDepartmentRepository(db_session).list_all()
        assert rows == [Department(id=1, name="Engineering")]
    elif table == "jobs":
        rows_j = SqlAlchemyJobRepository(db_session).list_all()
        assert rows_j == [Job(id=1, name="Recruiter")]
    elif table == "employees":
        (employee,) = SqlAlchemyEmployeeRepository(db_session).list_all()
        assert employee.employee_id == 1
        assert _millis(employee.hire_datetime) == _millis(UTC_NOW)
    elif table == "employee_versions":
        (version,) = SqlAlchemyEmployeeVersionRepository(db_session).list_all()
        assert version.employee_id == 1
        assert _millis(version.valid_from) == _millis(UTC_NOW)
    elif table == "loads":
        (load,) = SqlAlchemyLoadRepository(db_session).list_all()
        assert load.source == "historical"
    else:
        (record,) = SqlAlchemyRejectedRecordRepository(db_session).list_all()
        assert record.raw_payload == {"id": "x"}


def test_restore_preserves_identity_pks_for_loads(db_session: Session, tmp_path: Path) -> None:
    load_repo = SqlAlchemyLoadRepository(db_session)
    load1 = load_repo.create(Load(source="historical"))
    load2 = load_repo.create(Load(source="api:departments"))
    assert load1.id is not None and load2.id is not None
    backup = make_backup(db_session, tmp_path)
    restore = make_restore(db_session, tmp_path)
    backup.run("loads")

    load_repo.truncate()
    restore.run("loads")

    restored_ids = sorted(load.id for load in load_repo.list_all() if load.id is not None)
    assert restored_ids == sorted([load1.id, load2.id])


def test_restore_resyncs_identity_sequence_for_loads(
    db_session: Session, tmp_path: Path
) -> None:
    load_repo = SqlAlchemyLoadRepository(db_session)
    load = load_repo.create(Load(source="historical"))
    assert load.id is not None
    backup = make_backup(db_session, tmp_path)
    restore = make_restore(db_session, tmp_path)
    backup.run("loads")

    restore.run("loads")

    fresh = load_repo.create(Load(source="api:departments"))
    assert fresh.id is not None
    assert fresh.id > load.id


def test_restore_load_then_rejected_records_preserves_fk(
    db_session: Session, tmp_path: Path
) -> None:
    load = SqlAlchemyLoadRepository(db_session).create(Load(source="historical"))
    assert load.id is not None
    SqlAlchemyRejectedRecordRepository(db_session).add(
        RejectedRecord(
            target_table="departments",
            raw_payload={"id": "x"},
            reason_code=ReasonCode.MISSING_ID,
            message="id is empty",
            load_id=load.id,
        )
    )
    backup = make_backup(db_session, tmp_path)
    restore = make_restore(db_session, tmp_path)
    backup.run("loads")
    backup.run("rejected_records")

    restore.run("loads")
    restore.run("rejected_records")

    (record,) = SqlAlchemyRejectedRecordRepository(db_session).list_all()
    (restored_load,) = SqlAlchemyLoadRepository(db_session).list_all()
    assert record.load_id == restored_load.id == load.id


def test_full_six_table_restore_in_documented_order_succeeds(
    db_session: Session, tmp_path: Path
) -> None:
    seed_full_dataset(db_session)
    backup = make_backup(db_session, tmp_path)
    restore = make_restore(db_session, tmp_path)

    expected_counts = {
        "departments": len(SqlAlchemyDepartmentRepository(db_session).list_all()),
        "jobs": len(SqlAlchemyJobRepository(db_session).list_all()),
        "employees": len(SqlAlchemyEmployeeRepository(db_session).list_all()),
        "employee_versions": len(SqlAlchemyEmployeeVersionRepository(db_session).list_all()),
        "loads": len(SqlAlchemyLoadRepository(db_session).list_all()),
        "rejected_records": len(SqlAlchemyRejectedRecordRepository(db_session).list_all()),
    }

    for table in TABLE_NAMES:
        backup.run(table)

    for table in TABLE_NAMES:
        restore.run(table)

    assert len(SqlAlchemyDepartmentRepository(db_session).list_all()) == expected_counts[
        "departments"
    ]
    assert len(SqlAlchemyJobRepository(db_session).list_all()) == expected_counts["jobs"]
    assert len(SqlAlchemyEmployeeRepository(db_session).list_all()) == expected_counts[
        "employees"
    ]
    assert len(
        SqlAlchemyEmployeeVersionRepository(db_session).list_all()
    ) == expected_counts["employee_versions"]
    assert len(SqlAlchemyLoadRepository(db_session).list_all()) == expected_counts["loads"]
    assert len(
        SqlAlchemyRejectedRecordRepository(db_session).list_all()
    ) == expected_counts["rejected_records"]


def test_restore_out_of_order_raises_fk_violation(db_session: Session, tmp_path: Path) -> None:
    seed_full_dataset(db_session)
    backup = make_backup(db_session, tmp_path)
    restore = make_restore(db_session, tmp_path)
    backup.run("employees")

    # departments/jobs are still populated from seed_full_dataset here, so truncate them
    # (cascading away employees too) to simulate the genuinely out-of-order case: restoring
    # employees while its FK dependencies are empty.
    SqlAlchemyDepartmentRepository(db_session).truncate()
    SqlAlchemyJobRepository(db_session).truncate()

    with pytest.raises(IntegrityError):
        restore.run("employees")
