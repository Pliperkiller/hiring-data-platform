from dataclasses import FrozenInstanceError

import pytest

from app.domain.rejected_record import Load, RejectedRecord


def test_rejected_record_required_fields_only() -> None:
    record = RejectedRecord(
        target_table="hired_employees",
        raw_payload={"id": "", "name": "Alice"},
        reason_code="MISSING_ID",
        message="id is empty",
    )
    assert record.field is None
    assert record.load_id is None
    assert record.created_at is None
    assert record.id is None


def test_rejected_record_with_optional_fields() -> None:
    record = RejectedRecord(
        target_table="hired_employees",
        raw_payload={"id": "1"},
        reason_code="MISSING_NAME",
        message="name is empty",
        field="name",
        load_id=42,
    )
    assert record.field == "name"
    assert record.load_id == 42


def test_rejected_record_is_immutable() -> None:
    record = RejectedRecord(
        target_table="departments",
        raw_payload={},
        reason_code="MISSING_NAME",
        message="name is empty",
    )
    with pytest.raises(FrozenInstanceError):
        record.message = "changed"  # type: ignore[misc]


def test_load_defaults() -> None:
    load = Load(source="historical")
    assert load.accepted == 0
    assert load.rejected == 0
    assert load.finished_at is None
    assert load.id is None


def test_load_is_immutable() -> None:
    load = Load(source="historical")
    with pytest.raises(FrozenInstanceError):
        load.accepted = 5  # type: ignore[misc]
