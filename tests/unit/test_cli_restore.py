"""Unit tests for the restore CLI adapter's argv/table validation (no DB)."""

from __future__ import annotations

import pytest

from app.interface.cli.restore import main


def test_main_rejects_bad_argv_count_without_touching_the_db(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _fail_if_called(*args: object, **kwargs: object) -> None:
        raise AssertionError("build_engine must not be called for invalid argv")

    monkeypatch.setattr("app.infrastructure.db.session.build_engine", _fail_if_called)

    assert main(["restore.py"]) == 2
    assert main(["restore.py", "departments", "extra"]) == 2


def test_main_rejects_unknown_table_without_touching_the_db(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _fail_if_called(*args: object, **kwargs: object) -> None:
        raise AssertionError("build_engine must not be called for an unknown table")

    monkeypatch.setattr("app.infrastructure.db.session.build_engine", _fail_if_called)

    assert main(["restore.py", "bogus"]) == 2
