"""Pure admin-tab orchestration: build admin endpoint paths, interpret responses, gate access.

Thin HTTP client only, matching historical_load.py's decision: no imports from app.domain or
app.infrastructure, so the six table names are redeclared here rather than imported from
app.infrastructure.avro.tables. No network, no Streamlit — unit-testable in isolation, called
by the Streamlit page (real httpx post_fn) and by tests (fake post_fn).
"""

from __future__ import annotations

import secrets
from dataclasses import dataclass

from app.interface.ui.historical_load import PostResult

RESET_CONFIRMATION_TEXT = "RESET"

TABLE_NAMES: tuple[str, ...] = (
    "departments",
    "jobs",
    "employees",
    "employee_versions",
    "loads",
    "rejected_records",
)


def backup_endpoint(table: str) -> str:
    return f"/admin/backup/{table}"


def restore_endpoint(table: str) -> str:
    return f"/admin/restore/{table}"


@dataclass(frozen=True, slots=True)
class BackupOutcome:
    table: str
    success: bool
    path: str | None = None
    error_message: str | None = None


@dataclass(frozen=True, slots=True)
class RestoreOutcome:
    table: str
    success: bool
    restored: int | None = None
    error_message: str | None = None


def interpret_backup_result(table: str, result: PostResult) -> BackupOutcome:
    if result.error is not None or result.status_code != 200 or result.body is None:
        return BackupOutcome(
            table=table,
            success=False,
            error_message=result.error or f"HTTP {result.status_code}: {result.body}",
        )
    return BackupOutcome(table=table, success=True, path=result.body["path"])


def interpret_restore_result(table: str, result: PostResult) -> RestoreOutcome:
    if result.error is not None or result.status_code != 200 or result.body is None:
        return RestoreOutcome(
            table=table,
            success=False,
            error_message=result.error or f"HTTP {result.status_code}: {result.body}",
        )
    return RestoreOutcome(table=table, success=True, restored=result.body["restored"])


def reset_endpoint() -> str:
    return "/admin/reset"


@dataclass(frozen=True, slots=True)
class ResetOutcome:
    success: bool
    error_message: str | None = None


def interpret_reset_result(result: PostResult) -> ResetOutcome:
    if result.error is not None or result.status_code != 200 or result.body is None:
        return ResetOutcome(
            success=False,
            error_message=result.error or f"HTTP {result.status_code}: {result.body}",
        )
    return ResetOutcome(success=True)


def is_authenticated(entered: str, expected: str) -> bool:
    """Fails closed: an unset/empty ADMIN_PASSWORD never authenticates any input."""
    return bool(expected) and secrets.compare_digest(entered, expected)


def is_reset_confirmed(entered: str) -> bool:
    return entered == RESET_CONFIRMATION_TEXT


__all__ = [
    "RESET_CONFIRMATION_TEXT",
    "TABLE_NAMES",
    "BackupOutcome",
    "RestoreOutcome",
    "ResetOutcome",
    "backup_endpoint",
    "restore_endpoint",
    "reset_endpoint",
    "interpret_backup_result",
    "interpret_restore_result",
    "interpret_reset_result",
    "is_authenticated",
    "is_reset_confirmed",
]
