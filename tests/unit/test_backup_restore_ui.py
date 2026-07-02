"""Pure unit tests for the Streamlit backup/restore orchestration module. No Streamlit, no
network, no DB.
"""

from __future__ import annotations

from app.interface.ui.backup_restore import (
    TABLE_NAMES,
    backup_endpoint,
    interpret_backup_result,
    interpret_reset_result,
    interpret_restore_result,
    is_authenticated,
    is_reset_confirmed,
    reset_endpoint,
    restore_endpoint,
)
from app.interface.ui.historical_load import PostResult


def test_backup_endpoint_builds_admin_path() -> None:
    assert backup_endpoint("departments") == "/admin/backup/departments"


def test_restore_endpoint_builds_admin_path() -> None:
    assert restore_endpoint("departments") == "/admin/restore/departments"


def test_table_names_lists_all_six_tables() -> None:
    assert TABLE_NAMES == (
        "departments",
        "jobs",
        "employees",
        "employee_versions",
        "loads",
        "rejected_records",
    )


def test_interpret_backup_result_success() -> None:
    result = PostResult(status_code=200, body={"table": "departments", "path": "data/x.avro"})

    outcome = interpret_backup_result("departments", result)

    assert outcome.success is True
    assert outcome.path == "data/x.avro"
    assert outcome.error_message is None


def test_interpret_backup_result_http_error() -> None:
    result = PostResult(status_code=404, body={"error": {"code": "UNKNOWN_TABLE"}})

    outcome = interpret_backup_result("bogus", result)

    assert outcome.success is False
    assert "404" in (outcome.error_message or "")


def test_interpret_backup_result_network_error() -> None:
    result = PostResult(status_code=0, body=None, error="connection refused")

    outcome = interpret_backup_result("departments", result)

    assert outcome.success is False
    assert outcome.error_message == "connection refused"


def test_interpret_restore_result_success() -> None:
    result = PostResult(status_code=200, body={"table": "departments", "restored": 3})

    outcome = interpret_restore_result("departments", result)

    assert outcome.success is True
    assert outcome.restored == 3


def test_interpret_restore_result_failure() -> None:
    result = PostResult(status_code=500, body={"error": {"code": "INTERNAL_ERROR"}})

    outcome = interpret_restore_result("employees", result)

    assert outcome.success is False
    assert outcome.restored is None


def test_reset_endpoint_builds_admin_path() -> None:
    assert reset_endpoint() == "/admin/reset"


def test_interpret_reset_result_success() -> None:
    result = PostResult(status_code=200, body={"reset": True})

    outcome = interpret_reset_result(result)

    assert outcome.success is True
    assert outcome.error_message is None


def test_interpret_reset_result_http_error() -> None:
    result = PostResult(status_code=500, body={"error": {"code": "INTERNAL_ERROR"}})

    outcome = interpret_reset_result(result)

    assert outcome.success is False
    assert "500" in (outcome.error_message or "")


def test_interpret_reset_result_network_error() -> None:
    result = PostResult(status_code=0, body=None, error="connection refused")

    outcome = interpret_reset_result(result)

    assert outcome.success is False
    assert outcome.error_message == "connection refused"


def test_is_authenticated_correct_password() -> None:
    assert is_authenticated("hunter2", "hunter2") is True


def test_is_authenticated_wrong_password() -> None:
    assert is_authenticated("wrong", "hunter2") is False


def test_is_authenticated_fails_closed_when_expected_is_empty() -> None:
    assert is_authenticated("", "") is False
    assert is_authenticated("anything", "") is False


def test_is_reset_confirmed_requires_exact_text() -> None:
    assert is_reset_confirmed("RESET") is True
    assert is_reset_confirmed("reset") is False
    assert is_reset_confirmed("RESET ") is False
    assert is_reset_confirmed("") is False
