"""Pure unit tests for the historical-load orchestration: chunking, ordering, and
response aggregation. No Streamlit, no network, no DB."""

from __future__ import annotations

from typing import Any

import pytest

from app.interface.ui.historical_load import (
    BatchOutcome,
    LoadSummary,
    PostResult,
    TableName,
    chunk_rows,
    parse_headerless_csv,
    run_historical_load,
)


def _rows(n: int) -> list[dict[str, Any]]:
    return [{"id": i} for i in range(n)]


def _success_body(
    accepted: int, rejected: int, load_id: int = 1, rejected_rows: Any = ()
) -> dict[str, Any]:
    return {
        "load_id": load_id,
        "accepted": accepted,
        "rejected": rejected,
        "rejected_rows": list(rejected_rows),
    }


class TestChunkRows:
    def test_empty_input_returns_no_batches(self) -> None:
        assert chunk_rows([]) == []

    def test_fewer_rows_than_batch_size_is_one_batch(self) -> None:
        rows = _rows(5)
        assert chunk_rows(rows, batch_size=10) == [rows]

    def test_exact_batch_size_boundary_is_one_batch_no_trailing_empty(self) -> None:
        rows = _rows(1000)
        batches = chunk_rows(rows, batch_size=1000)
        assert len(batches) == 1
        assert len(batches[0]) == 1000

    def test_one_over_batch_size_produces_remainder_batch(self) -> None:
        rows = _rows(1001)
        batches = chunk_rows(rows, batch_size=1000)
        assert [len(b) for b in batches] == [1000, 1]

    def test_small_custom_batch_size_remainder(self) -> None:
        rows = _rows(5)
        batches = chunk_rows(rows, batch_size=2)
        assert [len(b) for b in batches] == [2, 2, 1]

    def test_batch_size_below_one_raises(self) -> None:
        with pytest.raises(ValueError, match="batch_size"):
            chunk_rows(_rows(3), batch_size=0)


class TestParseHeaderlessCsv:
    def test_zips_row_values_onto_columns_and_converts_id_to_int(self) -> None:
        rows = [["1", "Engineering"], ["2", "Sales"]]
        result = parse_headerless_csv(rows, "departments")
        assert result == [
            {"id": 1, "department": "Engineering"},
            {"id": 2, "department": "Sales"},
        ]

    def test_row_length_mismatch_raises(self) -> None:
        rows = [["1", "Engineering", "extra"]]
        with pytest.raises(ValueError):
            parse_headerless_csv(rows, "departments")

    def test_hired_employees_converts_id_department_id_job_id_to_int(self) -> None:
        rows = [["101", "Ada Lovelace", "2021-02-10T09:30:00Z", "1", "5"]]
        result = parse_headerless_csv(rows, "hired_employees")
        assert result == [
            {
                "id": 101,
                "name": "Ada Lovelace",
                "datetime": "2021-02-10T09:30:00Z",
                "department_id": 1,
                "job_id": 5,
            }
        ]

    def test_empty_or_non_numeric_int_column_is_left_as_string(self) -> None:
        rows = [["", "Ada Lovelace", "2021-02-10T09:30:00Z", "1", "5"]]
        result = parse_headerless_csv(rows, "hired_employees")
        assert result[0]["id"] == ""

    def test_name_and_datetime_columns_are_never_int_converted(self) -> None:
        rows = [["101", "42", "2021-02-10T09:30:00Z", "1", "5"]]
        result = parse_headerless_csv(rows, "hired_employees")
        assert result[0]["name"] == "42"


class TestRunHistoricalLoadOrdering:
    def test_posts_in_dependency_order_regardless_of_files_dict_order(self) -> None:
        calls: list[tuple[TableName, int]] = []

        def post_fn(table: TableName, batch: list[dict[str, Any]]) -> PostResult:
            calls.append((table, len(batch)))
            return PostResult(status_code=200, body=_success_body(len(batch), 0))

        files = {
            "hired_employees": _rows(1),
            "departments": _rows(1),
            "jobs": _rows(1),
        }

        run_historical_load(files, post_fn)

        assert [table for table, _ in calls] == ["departments", "jobs", "hired_employees"]

    def test_table_with_no_rows_contributes_zero_calls(self) -> None:
        calls: list[TableName] = []

        def post_fn(table: TableName, batch: list[dict[str, Any]]) -> PostResult:
            calls.append(table)
            return PostResult(status_code=200, body=_success_body(len(batch), 0))

        files: dict[TableName, list[dict[str, Any]]] = {"departments": _rows(1), "jobs": []}

        run_historical_load(files, post_fn)

        assert calls == ["departments"]


class TestRunHistoricalLoadAggregation:
    def test_totals_sum_across_multiple_batches_and_tables(self) -> None:
        def post_fn(table: TableName, batch: list[dict[str, Any]]) -> PostResult:
            return PostResult(
                status_code=200, body=_success_body(accepted=len(batch) - 1, rejected=1)
            )

        files = {"departments": _rows(3), "jobs": _rows(1)}

        summary = run_historical_load(files, post_fn, batch_size=2)

        # departments: batches of [2, 1] -> accepted (1 + 0) = 1, rejected 2
        # jobs: batch of [1] -> accepted 0, rejected 1
        assert summary.total_accepted == 1
        assert summary.total_rejected == 3

    def test_duplicate_row_index_across_batches_is_disambiguated(self) -> None:
        call_count = 0

        def post_fn(table: TableName, batch: list[dict[str, Any]]) -> PostResult:
            nonlocal call_count
            call_count += 1
            rejected_row = {
                "row_index": 0,
                "field": "id",
                "reason_code": "MISSING_ID",
                "message": "id is empty or not an integer",
            }
            return PostResult(
                status_code=200,
                body=_success_body(
                    accepted=0, rejected=1, load_id=call_count, rejected_rows=[rejected_row]
                ),
            )

        files = {"departments": _rows(4)}

        summary = run_historical_load(files, post_fn, batch_size=2)

        assert len(summary.rejected_rows) == 2
        first, second = summary.rejected_rows
        assert first.row_index == second.row_index == 0
        assert first.batch_index != second.batch_index
        assert first != second

    def test_file_row_computed_within_one_batch(self) -> None:
        def post_fn(table: TableName, batch: list[dict[str, Any]]) -> PostResult:
            rejected_row = {
                "row_index": 1,
                "field": "id",
                "reason_code": "MISSING_ID",
                "message": "id is empty or not an integer",
            }
            return PostResult(
                status_code=200,
                body=_success_body(accepted=1, rejected=1, rejected_rows=[rejected_row]),
            )

        files = {"departments": _rows(2)}

        summary = run_historical_load(files, post_fn, batch_size=2)

        assert len(summary.rejected_rows) == 1
        assert summary.rejected_rows[0].file_row == 2

    def test_file_row_at_exact_batch_size_boundary(self) -> None:
        def post_fn(table: TableName, batch: list[dict[str, Any]]) -> PostResult:
            row_index = 999 if len(batch) == 1000 else 0
            rejected_row = {
                "row_index": row_index,
                "field": "id",
                "reason_code": "MISSING_ID",
                "message": "id is empty or not an integer",
            }
            return PostResult(
                status_code=200,
                body=_success_body(
                    accepted=len(batch) - 1, rejected=1, rejected_rows=[rejected_row]
                ),
            )

        files = {"departments": _rows(1001)}

        summary = run_historical_load(files, post_fn, batch_size=1000)

        assert len(summary.rejected_rows) == 2
        first, second = summary.rejected_rows
        assert first.batch_index == 0
        assert first.row_index == 999
        assert first.file_row == 1000
        assert second.batch_index == 1
        assert second.row_index == 0
        assert second.file_row == 1001

    def test_raw_payload_matches_the_exact_submitted_row(self) -> None:
        def post_fn(table: TableName, batch: list[dict[str, Any]]) -> PostResult:
            rejected_row = {
                "row_index": 2,
                "field": "id",
                "reason_code": "MISSING_ID",
                "message": "id is empty or not an integer",
            }
            return PostResult(
                status_code=200,
                body=_success_body(accepted=2, rejected=1, rejected_rows=[rejected_row]),
            )

        files = {"departments": _rows(3)}

        summary = run_historical_load(files, post_fn, batch_size=3)

        assert summary.rejected_rows[0].raw_payload == {"id": 2}


class TestRunHistoricalLoadFailureHandling:
    def test_raising_post_fn_is_recorded_as_failed_batch_and_run_continues(self) -> None:
        def post_fn(table: TableName, batch: list[dict[str, Any]]) -> PostResult:
            if table == "departments" and len(batch) == 1 and batch[0]["id"] == 2:
                raise RuntimeError("boom")
            return PostResult(status_code=200, body=_success_body(len(batch), 0))

        files = {"departments": _rows(4)}

        summary = run_historical_load(files, post_fn, batch_size=1)

        assert len(summary.batch_outcomes) == 4
        failed = summary.failed_batches
        assert len(failed) == 1
        assert failed[0].table == "departments"
        assert failed[0].batch_index == 2
        assert failed[0].error_message is not None
        assert "boom" in failed[0].error_message
        successful = [o for o in summary.batch_outcomes if o.success]
        assert len(successful) == 3

    def test_non_200_status_without_exception_is_recorded_as_failed(self) -> None:
        def post_fn(table: TableName, batch: list[dict[str, Any]]) -> PostResult:
            return PostResult(status_code=500, body=None)

        summary = run_historical_load({"departments": _rows(1)}, post_fn)

        assert len(summary.failed_batches) == 1
        assert summary.failed_batches[0].success is False

    def test_reference_table_failure_flag(self) -> None:
        def failing_post_fn(table: TableName, batch: list[dict[str, Any]]) -> PostResult:
            if table == "departments":
                return PostResult(status_code=500, body=None)
            return PostResult(status_code=200, body=_success_body(len(batch), 0))

        files = {"departments": _rows(1), "jobs": _rows(1), "hired_employees": _rows(1)}

        failing_summary = run_historical_load(files, failing_post_fn)
        assert failing_summary.reference_table_failed is True

        def all_ok_post_fn(table: TableName, batch: list[dict[str, Any]]) -> PostResult:
            return PostResult(status_code=200, body=_success_body(len(batch), 0))

        ok_summary = run_historical_load(files, all_ok_post_fn)
        assert ok_summary.reference_table_failed is False

    def test_on_progress_called_once_per_batch_in_order(self) -> None:
        seen: list[BatchOutcome] = []

        def post_fn(table: TableName, batch: list[dict[str, Any]]) -> PostResult:
            return PostResult(status_code=200, body=_success_body(len(batch), 0))

        files = {"departments": _rows(3), "jobs": _rows(1)}

        summary = run_historical_load(files, post_fn, batch_size=1, on_progress=seen.append)

        assert seen == list(summary.batch_outcomes)


def test_load_summary_defaults_are_empty() -> None:
    summary = LoadSummary()
    assert summary.total_accepted == 0
    assert summary.total_rejected == 0
    assert summary.failed_batches == ()
    assert summary.reference_table_failed is False
