"""Concrete BackupCodec backed by fastavro, wrapping codec.py's dict<->AVRO helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.domain.backup_codec import BackupCodec
from app.infrastructure.avro.codec import from_avro_dicts, read_avro, to_avro_dicts, write_avro


class AvroBackupCodec(BackupCodec):
    def write(self, table: str, rows: list[Any], path: Path) -> None:
        write_avro(table, to_avro_dicts(table, rows), path)

    def read(self, table: str, path: Path) -> list[Any]:
        return from_avro_dicts(table, read_avro(path))


__all__ = ["AvroBackupCodec"]
