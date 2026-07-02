"""Unit tests for the domain-level backup/restore table validation (no DB, no AVRO)."""

from __future__ import annotations

import pytest

from app.domain.backup_codec import TABLE_NAMES, validate_table_name


def test_validate_table_name_rejects_unknown_table() -> None:
    with pytest.raises(ValueError):
        validate_table_name("bogus")


def test_validate_table_name_accepts_all_known_tables() -> None:
    for table in TABLE_NAMES:
        validate_table_name(table)
