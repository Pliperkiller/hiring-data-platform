import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.domain.rejected_record import Load, RejectedRecord
from app.domain.value_objects import ReasonCode
from app.infrastructure.db.repositories import (
    SqlAlchemyLoadRepository,
    SqlAlchemyRejectedRecordRepository,
)

pytestmark = pytest.mark.usefixtures("apply_migrations")


def test_add_round_trips_raw_payload(db_session: Session) -> None:
    repo = SqlAlchemyRejectedRecordRepository(db_session)
    payload = {"id": "", "name": "Alice", "department_id": "1"}

    added = repo.add(
        RejectedRecord(
            target_table="hired_employees",
            raw_payload=payload,
            reason_code=ReasonCode.MISSING_ID,
            message="id is empty",
            field="id",
        )
    )

    assert added.id is not None
    assert added.raw_payload == payload
    assert added.created_at is not None


def test_add_with_load_id_none_succeeds(db_session: Session) -> None:
    repo = SqlAlchemyRejectedRecordRepository(db_session)

    added = repo.add(
        RejectedRecord(
            target_table="departments",
            raw_payload={},
            reason_code=ReasonCode.MISSING_NAME,
            message="name is empty",
        )
    )

    assert added.load_id is None


def test_add_with_valid_load_id_and_list_for_load(db_session: Session) -> None:
    load = SqlAlchemyLoadRepository(db_session).create(Load(source="historical"))
    assert load.id is not None
    repo = SqlAlchemyRejectedRecordRepository(db_session)

    repo.add(
        RejectedRecord(
            target_table="hired_employees",
            raw_payload={"id": "1"},
            reason_code=ReasonCode.MISSING_NAME,
            message="name is empty",
            load_id=load.id,
        )
    )

    records = repo.list_for_load(load.id)
    assert len(records) == 1
    assert records[0].load_id == load.id


def test_add_with_unknown_load_id_raises_integrity_error(db_session: Session) -> None:
    repo = SqlAlchemyRejectedRecordRepository(db_session)

    with pytest.raises(IntegrityError):
        repo.add(
            RejectedRecord(
                target_table="hired_employees",
                raw_payload={},
                reason_code=ReasonCode.MISSING_NAME,
                message="name is empty",
                load_id=999,
            )
        )
