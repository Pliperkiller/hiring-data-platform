"""RejectedRecord and Load entities.

Load is co-located here rather than in a separate module: docs/DESIGN.md's folder layout
does not reserve a slot for it, and it is relationally coupled to RejectedRecord
(rejected_records.load_id -> loads.id), both populated during ingestion/rejection.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass(frozen=True, slots=True)
class Load:
    source: str
    started_at: datetime | None = None
    finished_at: datetime | None = None
    accepted: int = 0
    rejected: int = 0
    id: int | None = None


@dataclass(frozen=True, slots=True)
class RejectedRecord:
    target_table: str
    raw_payload: dict[str, Any]
    # reason_code is a plain str in this phase; feature/validation narrows it to the
    # ReasonCode catalog in app/domain/value_objects.py.
    reason_code: str
    message: str
    field: str | None = None
    load_id: int | None = None
    created_at: datetime | None = None
    id: int | None = None
