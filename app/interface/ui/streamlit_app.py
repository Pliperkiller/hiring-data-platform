"""Streamlit UI: historical load and backup/restore (docs/DESIGN.md, docs/DECISIONS.md
"Option B" and the backup/restore HTTP-endpoint reversal).

Thin HTTP client only: no imports from app.domain or app.infrastructure. Talks to the API
over HTTP exactly as any other client would, so validation/orchestration is never
reimplemented here — it is delegated to the API and to the pure orchestration modules
(historical_load.py, backup_restore.py).
"""

from __future__ import annotations

import csv
import io
import os
from typing import Any

import httpx
import streamlit as st

from app.interface.ingest_constants import MAX_BATCH_SIZE
from app.interface.ui.backup_restore import (
    TABLE_NAMES,
    BackupOutcome,
    RestoreOutcome,
    backup_endpoint,
    interpret_backup_result,
    interpret_restore_result,
    restore_endpoint,
)
from app.interface.ui.historical_load import (
    BatchOutcome,
    LoadSummary,
    PostResult,
    TableName,
    parse_headerless_csv,
    run_historical_load,
)

API_BASE_URL = os.environ.get("API_BASE_URL", "http://localhost:8000")

_ENDPOINT_BY_TABLE: dict[TableName, str] = {
    "departments": "/ingest/departments",
    "jobs": "/ingest/jobs",
    "hired_employees": "/ingest/hired_employees",
}


def _read_headerless_csv(uploaded_file: Any, table: TableName) -> list[dict[str, Any]] | None:
    """Decode and parse one uploaded CSV. Returns None (after showing an st.error) if the
    file can't be decoded as ASCII — the real challenge CSVs are documented as ASCII in
    docs/DATA_MODEL.md, but an unexpected upload must fail visibly, not with a raw
    traceback."""
    try:
        text = uploaded_file.getvalue().decode("ascii")
    except UnicodeDecodeError:
        st.error(
            f"{uploaded_file.name}: could not decode as ASCII — check the file matches "
            "the expected export format."
        )
        return None
    reader = csv.reader(io.StringIO(text))
    rows = [row for row in reader if row]
    return parse_headerless_csv(rows, table)


def _build_post_fn(client: httpx.Client) -> Any:
    def post_fn(table: TableName, batch: list[dict[str, Any]]) -> PostResult:
        try:
            response = client.post(_ENDPOINT_BY_TABLE[table], json=batch)
        except httpx.HTTPError as exc:
            return PostResult(status_code=0, body=None, error=str(exc))
        try:
            body = response.json()
        except ValueError:
            body = None
        return PostResult(status_code=response.status_code, body=body)

    return post_fn


def render_historical_load() -> None:
    st.title("Historical Load")
    st.caption(
        f"Uploads are chunked into batches of up to {MAX_BATCH_SIZE} rows and posted to "
        f"{API_BASE_URL} in dependency order: departments, jobs, hired_employees."
    )

    uploads: dict[TableName, Any] = {
        "departments": st.file_uploader("departments.csv", type="csv", key="departments"),
        "jobs": st.file_uploader("jobs.csv", type="csv", key="jobs"),
        "hired_employees": st.file_uploader(
            "hired_employees.csv", type="csv", key="hired_employees"
        ),
    }

    if st.button("Run historical load", disabled=not any(uploads.values())):
        files: dict[TableName, list[dict[str, Any]]] = {}
        for table, uploaded_file in uploads.items():
            if uploaded_file is None:
                continue
            rows = _read_headerless_csv(uploaded_file, table)
            if rows is not None:
                files[table] = rows

        total_batches = sum(-(-len(rows) // MAX_BATCH_SIZE) for rows in files.values()) or 1
        progress = st.progress(0.0)
        totals_placeholder = st.empty()
        state = {"done": 0, "accepted": 0, "rejected": 0, "failed": 0}

        def on_progress(outcome: BatchOutcome) -> None:
            state["done"] += 1
            state["accepted"] += outcome.accepted
            state["rejected"] += outcome.rejected
            state["failed"] += 0 if outcome.success else 1
            progress.progress(min(state["done"] / total_batches, 1.0))
            with totals_placeholder.container():
                st.write(
                    f"Batches processed: {state['done']}/{total_batches} · "
                    f"Accepted: {state['accepted']} · Rejected: {state['rejected']} · "
                    f"Failed batches: {state['failed']}"
                )

        with httpx.Client(base_url=API_BASE_URL, timeout=30.0) as client:
            new_summary = run_historical_load(
                files=files,
                post_fn=_build_post_fn(client),
                batch_size=MAX_BATCH_SIZE,
                on_progress=on_progress,
            )

        st.session_state["last_summary"] = new_summary

    last_summary: LoadSummary | None = st.session_state.get("last_summary")
    if last_summary is not None:
        _render_summary(last_summary)


def _render_summary(summary: LoadSummary) -> None:
    st.subheader("Summary")
    st.write(
        f"Total accepted: {summary.total_accepted} · "
        f"Total rejected: {summary.total_rejected} · "
        f"Failed batches: {len(summary.failed_batches)}"
    )

    if summary.reference_table_failed:
        st.warning(
            "A departments or jobs batch failed. Hire rows may show UNKNOWN_DEPARTMENT/"
            "UNKNOWN_JOB rejections as a downstream consequence, not because the hire data "
            "itself is invalid. Re-run the failed reference-table batch(es) below, then "
            "re-run hired_employees."
        )

    if summary.failed_batches:
        st.subheader("Failed batches")
        st.caption(
            "A failed batch (e.g. the API wasn't reachable yet) is not retried "
            "automatically — re-run the historical load once the issue is resolved."
        )
        st.table(
            [
                {
                    "table": o.table,
                    "batch_index": o.batch_index,
                    "rows": o.row_count,
                    "error": o.error_message,
                }
                for o in summary.failed_batches
            ]
        )

    if summary.rejected_rows:
        st.subheader("Rejected rows")
        tables = sorted({r.table for r in summary.rejected_rows})
        reason_codes = sorted({r.reason_code for r in summary.rejected_rows})
        table_filter = st.multiselect("Filter by table", tables, default=tables)
        reason_filter = st.multiselect("Filter by reason code", reason_codes, default=reason_codes)

        filtered = [
            r
            for r in summary.rejected_rows
            if r.table in table_filter and r.reason_code in reason_filter
        ]
        st.dataframe(
            [
                {
                    "table": r.table,
                    "batch_index": r.batch_index,
                    "row_index": r.row_index,
                    "field": r.field,
                    "reason_code": r.reason_code,
                    "message": r.message,
                }
                for r in filtered
            ]
        )


def _build_admin_post_fn(client: httpx.Client) -> Any:
    def post_fn(path: str) -> PostResult:
        try:
            response = client.post(path)
        except httpx.HTTPError as exc:
            return PostResult(status_code=0, body=None, error=str(exc))
        try:
            body = response.json()
        except ValueError:
            body = None
        return PostResult(status_code=response.status_code, body=body)

    return post_fn


def render_backup_restore() -> None:
    st.title("Backup & Restore")
    st.caption(
        f"Backs up or restores one table at a time via {API_BASE_URL}/admin/*. Restore is a "
        "full replace (truncate + insert) and cannot be undone. These endpoints have no "
        "authentication of their own — see docs/DECISIONS.md — so this page's confirmation "
        "checkbox is a UI-level safeguard, not a substitute for restricting /admin/* at the "
        "network level in a real deployment."
    )

    with httpx.Client(base_url=API_BASE_URL, timeout=30.0) as client:
        post_fn = _build_admin_post_fn(client)

        for table in TABLE_NAMES:
            st.subheader(table)
            col_backup, col_restore = st.columns(2)

            with col_backup:
                if st.button(f"Backup {table}", key=f"backup_{table}"):
                    result = post_fn(backup_endpoint(table))
                    st.session_state[f"backup_outcome_{table}"] = interpret_backup_result(
                        table, result
                    )

                backup_outcome: BackupOutcome | None = st.session_state.get(
                    f"backup_outcome_{table}"
                )
                if backup_outcome is not None:
                    if backup_outcome.success:
                        st.success(f"Backed up to {backup_outcome.path}")
                    else:
                        st.error(backup_outcome.error_message)

            with col_restore:
                confirmed = st.checkbox(
                    f"I understand this replaces all data in {table}",
                    key=f"confirm_restore_{table}",
                )
                if st.button(
                    f"Restore {table}", key=f"restore_{table}", disabled=not confirmed
                ):
                    result = post_fn(restore_endpoint(table))
                    st.session_state[f"restore_outcome_{table}"] = interpret_restore_result(
                        table, result
                    )

                restore_outcome: RestoreOutcome | None = st.session_state.get(
                    f"restore_outcome_{table}"
                )
                if restore_outcome is not None:
                    if restore_outcome.success:
                        st.success(f"Restored {restore_outcome.restored} row(s)")
                    else:
                        st.error(restore_outcome.error_message)


tab_historical_load, tab_backup_restore = st.tabs(["Historical Load", "Backup & Restore"])
with tab_historical_load:
    render_historical_load()
with tab_backup_restore:
    render_backup_restore()
