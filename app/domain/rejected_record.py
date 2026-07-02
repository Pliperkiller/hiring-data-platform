"""RejectedRecord and Load entities.

Load is co-located here rather than in a separate module: docs/DESIGN.md's folder layout
does not reserve a slot for it, and it is relationally coupled to RejectedRecord
(rejected_records.load_id -> loads.id), both populated during ingestion/rejection.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from app.domain.value_objects import ReasonCode


@dataclass(frozen=True, slots=True)
class Load:
    source: str
    started_at: datetime | None = None
    finished_at: datetime | None = None
    accepted: int = 0
    rejected: int = 0
    id: int | None = None


@dataclass(frozen=True, slots=True)
class LoadStats:
    """Aggregate over finished loads with started_at >= some `since` cutoff."""

    total_loads: int
    total_accepted: int
    total_rejected: int
    average_reject_rate: float

    @staticmethod
    def compute(total_loads: int, total_accepted: int, total_rejected: int) -> LoadStats:
        total_rows = total_accepted + total_rejected
        # No finished loads (or all-empty batches) in the window: 0.0, not a ZeroDivisionError.
        reject_rate = total_rejected / total_rows if total_rows else 0.0
        return LoadStats(
            total_loads=total_loads,
            total_accepted=total_accepted,
            total_rejected=total_rejected,
            average_reject_rate=reject_rate,
        )


@dataclass(frozen=True, slots=True)
class RejectedRecord:
    target_table: str
    raw_payload: dict[str, Any]
    reason_code: ReasonCode
    message: str
    field: str | None = None
    load_id: int | None = None
    created_at: datetime | None = None
    id: int | None = None
