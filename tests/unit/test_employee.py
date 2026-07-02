from dataclasses import FrozenInstanceError
from datetime import UTC, datetime

import pytest

from app.domain.employee import Employee, EmployeeVersion


def make_employee(**overrides: object) -> Employee:
    defaults: dict[str, object] = {
        "employee_id": 1,
        "name_at_hire": "Alice",
        "hire_datetime": datetime(2021, 3, 15, tzinfo=UTC),
        "hire_department_id": 10,
        "hire_job_id": 20,
    }
    defaults.update(overrides)
    return Employee(**defaults)  # type: ignore[arg-type]


def make_version(**overrides: object) -> EmployeeVersion:
    defaults: dict[str, object] = {
        "employee_id": 1,
        "name": "Alice",
        "department_id": 10,
        "job_id": 20,
        "valid_from": datetime(2021, 3, 15, tzinfo=UTC),
        "valid_to": None,
        "is_current": True,
    }
    defaults.update(overrides)
    return EmployeeVersion(**defaults)  # type: ignore[arg-type]


def test_employee_equality() -> None:
    assert make_employee() == make_employee()
    assert make_employee(name_at_hire="Bob") != make_employee()


def test_employee_is_immutable() -> None:
    employee = make_employee()
    with pytest.raises(FrozenInstanceError):
        employee.name_at_hire = "Bob"  # type: ignore[misc]


def test_employee_first_loaded_at_defaults_to_none() -> None:
    assert make_employee().first_loaded_at is None


def test_tracked_attributes() -> None:
    version = make_version()
    assert version.tracked_attributes == ("Alice", 10, 20)


@pytest.mark.parametrize(
    ("name", "department_id", "job_id", "expected"),
    [
        ("Alice", 10, 20, False),
        ("Bob", 10, 20, True),
        ("Alice", 99, 20, True),
        ("Alice", 10, 99, True),
    ],
)
def test_has_changed(name: str, department_id: int, job_id: int, expected: bool) -> None:
    version = make_version()
    assert version.has_changed(name, department_id, job_id) is expected


def test_open_version() -> None:
    version = make_version()
    assert version.valid_to is None
    assert version.is_current is True


def test_closed_version() -> None:
    version = make_version(
        valid_to=datetime(2021, 6, 1, tzinfo=UTC), is_current=False
    )
    assert version.valid_to is not None
    assert version.is_current is False


def test_version_is_immutable() -> None:
    version = make_version()
    with pytest.raises(FrozenInstanceError):
        version.is_current = False  # type: ignore[misc]
