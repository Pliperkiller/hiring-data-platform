"""Request / response Pydantic schemas for the ingestion and reports APIs (docs/API_CONTRACT.md).

Row-level models deliberately do NOT type-check field content (id/department/job/name/
datetime/department_id/job_id all accept Any). app/domain/validation.ValidationService is the
single source of truth for field-level correctness (a string id, a bad datetime, etc. must
become a MISSING_ID/BAD_DATETIME_FORMAT reason code in a 200 partial-success response, never a
422 for the whole batch). Pydantic's job here is only the envelope: confirm the body is a JSON
array of JSON objects, and enforce the 1-1000 length bound.
"""

from __future__ import annotations

from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field

from app.interface.ingest_constants import MAX_BATCH_SIZE, MIN_BATCH_SIZE


class DepartmentIn(BaseModel):
    model_config = ConfigDict(
        extra="allow", json_schema_extra={"example": {"id": 1, "department": "Engineering"}}
    )

    id: Any = None
    department: Any = None


class JobIn(BaseModel):
    model_config = ConfigDict(
        extra="allow", json_schema_extra={"example": {"id": 1, "job": "Recruiter"}}
    )

    id: Any = None
    job: Any = None


class HireIn(BaseModel):
    model_config = ConfigDict(
        extra="allow",
        json_schema_extra={
            "example": {
                "id": 101,
                "name": "Ada Lovelace",
                "datetime": "2021-02-10T09:30:00Z",
                "department_id": 1,
                "job_id": 5,
            }
        },
    )

    id: Any = None
    name: Any = None
    datetime: Any = None
    department_id: Any = None
    job_id: Any = None


DepartmentBatch = Annotated[
    list[DepartmentIn], Field(min_length=MIN_BATCH_SIZE, max_length=MAX_BATCH_SIZE)
]
JobBatch = Annotated[list[JobIn], Field(min_length=MIN_BATCH_SIZE, max_length=MAX_BATCH_SIZE)]
HireBatch = Annotated[list[HireIn], Field(min_length=MIN_BATCH_SIZE, max_length=MAX_BATCH_SIZE)]


class RejectedRowOut(BaseModel):
    row_index: int
    field: str | None
    reason_code: str
    message: str


class IngestResponse(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "load_id": 42,
                "accepted": 950,
                "rejected": 2,
                "rejected_rows": [
                    {
                        "row_index": 3,
                        "field": "job_id",
                        "reason_code": "MISSING_JOB",
                        "message": "job_id is empty",
                    },
                    {
                        "row_index": 7,
                        "field": "department_id",
                        "reason_code": "UNKNOWN_DEPARTMENT",
                        "message": "department_id 999 does not exist",
                    },
                ],
            }
        }
    )

    load_id: int
    accepted: int
    rejected: int
    rejected_rows: list[RejectedRowOut] = []


class HiresByQuarterOut(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "department": "Engineering",
                "job": "Software Engineer",
                "Q1": 3,
                "Q2": 5,
                "Q3": 2,
                "Q4": 4,
            }
        }
    )

    department: str
    job: str
    Q1: int
    Q2: int
    Q3: int
    Q4: int


class DepartmentAboveAverageOut(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={"example": {"id": 8, "department": "Support", "hired": 216}}
    )

    id: int
    department: str
    hired: int


class BackupOut(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={"example": {"table": "departments", "path": "data/departments.avro"}}
    )

    table: str
    path: str


class RestoreOut(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={"example": {"table": "departments", "restored": 12}}
    )

    table: str
    restored: int


class ResetOut(BaseModel):
    model_config = ConfigDict(json_schema_extra={"example": {"reset": True}})

    reset: bool = True


class ErrorDetail(BaseModel):
    code: str
    message: str
    detail: dict[str, Any] | None = None


class ErrorBody(BaseModel):
    error: ErrorDetail
