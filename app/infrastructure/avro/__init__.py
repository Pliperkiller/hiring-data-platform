"""AVRO backup/restore serialization. See docs/BACKUP_RESTORE.md."""

from app.domain.backup_codec import TABLE_NAMES, validate_table_name
from app.infrastructure.avro.avro_backup_codec import AvroBackupCodec
from app.infrastructure.avro.codec import from_avro_dicts, read_avro, to_avro_dicts, write_avro

__all__ = [
    "TABLE_NAMES",
    "validate_table_name",
    "AvroBackupCodec",
    "write_avro",
    "read_avro",
    "to_avro_dicts",
    "from_avro_dicts",
]
