"""Pure historical-load orchestration: chunk CSV rows, POST them in dependency order,
aggregate results. No Streamlit, no network, no DB import here — this module is
unit-testable in isolation and is called by both the Streamlit page (real httpx post_fn)
and integration tests (TestClient.post-backed post_fn).
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from typing import Any

from app.interface.ingest_constants import MAX_BATCH_SIZE

TableName = str  # "departments" | "jobs" | "hired_employees"

# Dependency order: reference tables before employees (FK dependency).
TABLE_ORDER: tuple[TableName, ...] = ("departments", "jobs", "hired_employees")

TABLE_COLUMNS: dict[TableName, tuple[str, ...]] = {
    "departments": ("id", "department"),
    "jobs": ("id", "job"),
    "hired_employees": ("id", "name", "datetime", "department_id", "job_id"),
}

# Columns the API requires as JSON integers (ValidationService does a strict `type(value)
# is not int` check, by design — see docs/DECISIONS.md "no string coercion"). A headerless
# CSV yields plain strings for every field, so the client must convert these before POSTing;
# the API is not responsible for parsing digit-strings itself.
_INT_COLUMNS: dict[TableName, frozenset[str]] = {
    "departments": frozenset({"id"}),
    "jobs": frozenset({"id"}),
    "hired_employees": frozenset({"id", "department_id", "job_id"}),
}


@dataclass(frozen=True, slots=True)
class PostResult:
    """Adapter-agnostic view of one HTTP call's outcome.

    A plain dataclass rather than an httpx.Response/TestClient Response lets unit tests
    fake post_fn without constructing a real response object, while integration tests and
    the real Streamlit page can both trivially adapt their client's response into this
    shape.
    """

    status_code: int
    body: dict[str, Any] | None  # parsed JSON body; None if the call itself failed
    error: str | None = None  # set when the call raised (network error, timeout, ...)


# post_fn contract: (table, batch_rows) -> outcome of that HTTP call.
PostFn = Callable[[TableName, list[dict[str, Any]]], PostResult]


@dataclass(frozen=True, slots=True)
class RejectedRowSummary:
    """One rejected-row entry, disambiguated across tables and batches.

    The API's row_index is only unique within one batch's response; (table, batch_index,
    row_index) is the key that disambiguates it across a whole historical-load run.
    """

    table: TableName
    batch_index: int
    row_index: int
    field: str | None
    reason_code: str
    message: str


@dataclass(frozen=True, slots=True)
class BatchOutcome:
    """Outcome of one POST call for one batch of one table."""

    table: TableName
    batch_index: int
    row_count: int
    success: bool
    accepted: int = 0
    rejected: int = 0
    load_id: int | None = None
    error_message: str | None = None


@dataclass(frozen=True, slots=True)
class LoadSummary:
    """Aggregated result of a full historical-load run across all three tables."""

    batch_outcomes: tuple[BatchOutcome, ...] = field(default_factory=tuple)
    rejected_rows: tuple[RejectedRowSummary, ...] = field(default_factory=tuple)

    @property
    def total_accepted(self) -> int:
        return sum(o.accepted for o in self.batch_outcomes)

    @property
    def total_rejected(self) -> int:
        return sum(o.rejected for o in self.batch_outcomes)

    @property
    def failed_batches(self) -> tuple[BatchOutcome, ...]:
        return tuple(o for o in self.batch_outcomes if not o.success)

    @property
    def reference_table_failed(self) -> bool:
        """True if any departments/jobs batch failed — later hire rejections may cascade
        from this (UNKNOWN_DEPARTMENT/UNKNOWN_JOB), not from bad hire data itself."""
        return any(
            not o.success and o.table in ("departments", "jobs") for o in self.batch_outcomes
        )


ProgressCallback = Callable[[BatchOutcome], None]


def _coerce_field(value: str, column: str, int_columns: frozenset[str]) -> Any:
    if column not in int_columns:
        return value
    try:
        return int(value)
    except ValueError:
        # Empty or malformed — left as the original string so the API's own MISSING_*
        # check (type(value) is not int) still rejects it with the correct reason code,
        # rather than this client silently fabricating a value.
        return value


def parse_headerless_csv(raw_rows: Iterable[list[str]], table: TableName) -> list[dict[str, Any]]:
    """Zip headerless CSV rows (already split into string fields) onto the table's column
    names, in the fixed order documented in docs/DATA_MODEL.md, converting id/department_id/
    job_id to JSON integers (the API requires real ints for these, not digit-strings — see
    _INT_COLUMNS). Does not otherwise validate values — that is the API's job (Pydantic
    envelope + ValidationService)."""
    columns = TABLE_COLUMNS[table]
    int_columns = _INT_COLUMNS[table]
    return [
        {
            column: _coerce_field(value, column, int_columns)
            for column, value in zip(columns, row, strict=True)
        }
        for row in raw_rows
    ]


def chunk_rows(
    rows: list[dict[str, Any]], batch_size: int = MAX_BATCH_SIZE
) -> list[list[dict[str, Any]]]:
    """Split rows into batches of at most batch_size (default MAX_BATCH_SIZE)."""
    if batch_size < 1:
        raise ValueError("batch_size must be >= 1")
    return [rows[i : i + batch_size] for i in range(0, len(rows), batch_size)]


def _outcome_from_post_result(
    table: TableName, batch_index: int, row_count: int, result: PostResult
) -> tuple[BatchOutcome, list[RejectedRowSummary]]:
    if result.error is not None or result.status_code != 200 or result.body is None:
        message = result.error or f"HTTP {result.status_code}: {result.body}"
        return (
            BatchOutcome(
                table=table,
                batch_index=batch_index,
                row_count=row_count,
                success=False,
                error_message=message,
            ),
            [],
        )

    body = result.body
    rejected_rows = [
        RejectedRowSummary(
            table=table,
            batch_index=batch_index,
            row_index=r["row_index"],
            field=r.get("field"),
            reason_code=r["reason_code"],
            message=r["message"],
        )
        for r in body.get("rejected_rows", [])
    ]
    outcome = BatchOutcome(
        table=table,
        batch_index=batch_index,
        row_count=row_count,
        success=True,
        accepted=body["accepted"],
        rejected=body["rejected"],
        load_id=body["load_id"],
    )
    return outcome, rejected_rows


def run_historical_load(
    files: dict[TableName, list[dict[str, Any]]],
    post_fn: PostFn,
    batch_size: int = MAX_BATCH_SIZE,
    on_progress: ProgressCallback | None = None,
) -> LoadSummary:
    """Chunk each table's rows and POST them in TABLE_ORDER.

    A batch that fails (post_fn raises, or returns a non-200 PostResult) is recorded as a
    failed BatchOutcome and processing continues with the next batch (and, after a table
    finishes, the next table) rather than aborting the whole run.
    """
    outcomes: list[BatchOutcome] = []
    rejected: list[RejectedRowSummary] = []

    for table in TABLE_ORDER:
        rows = files.get(table, [])
        if not rows:
            continue
        for batch_index, batch in enumerate(chunk_rows(rows, batch_size)):
            try:
                result = post_fn(table, batch)
            except Exception as exc:
                result = PostResult(status_code=0, body=None, error=str(exc))

            outcome, batch_rejected = _outcome_from_post_result(
                table, batch_index, len(batch), result
            )
            outcomes.append(outcome)
            rejected.extend(batch_rejected)
            if on_progress is not None:
                on_progress(outcome)

    return LoadSummary(batch_outcomes=tuple(outcomes), rejected_rows=tuple(rejected))


__all__ = [
    "TABLE_COLUMNS",
    "TABLE_ORDER",
    "BatchOutcome",
    "LoadSummary",
    "PostFn",
    "PostResult",
    "RejectedRowSummary",
    "TableName",
    "chunk_rows",
    "parse_headerless_csv",
    "run_historical_load",
]
