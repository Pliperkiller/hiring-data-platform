"""AVRO backup/restore serialization. See docs/BACKUP_RESTORE.md."""

from app.infrastructure.avro.codec import from_avro_dicts, read_avro, to_avro_dicts, write_avro
from app.infrastructure.avro.tables import TABLE_NAMES, validate_table_name

__all__ = [
    "TABLE_NAMES",
    "validate_table_name",
    "write_avro",
    "read_avro",
    "to_avro_dicts",
    "from_avro_dicts",
]
