from dataclasses import FrozenInstanceError

import pytest

from app.domain.reference import Department, Job


def test_department_equality() -> None:
    assert Department(id=1, name="Engineering") == Department(id=1, name="Engineering")
    assert Department(id=1, name="Engineering") != Department(id=1, name="Sales")


def test_department_is_immutable() -> None:
    department = Department(id=1, name="Engineering")
    with pytest.raises(FrozenInstanceError):
        department.name = "Sales"  # type: ignore[misc]


def test_job_equality() -> None:
    assert Job(id=1, name="Recruiter") == Job(id=1, name="Recruiter")
    assert Job(id=1, name="Recruiter") != Job(id=2, name="Recruiter")


def test_job_is_immutable() -> None:
    job = Job(id=1, name="Recruiter")
    with pytest.raises(FrozenInstanceError):
        job.name = "Engineer"  # type: ignore[misc]
