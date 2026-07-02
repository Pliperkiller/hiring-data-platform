"""Reference catalogs: Department, Job.

Upserted by id (insert, or update the name if changed) during ingestion — see
docs/DATA_MODEL.md. No validation here; that is feature/validation's job.
"""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Department:
    id: int
    name: str


@dataclass(frozen=True, slots=True)
class Job:
    id: int
    name: str
