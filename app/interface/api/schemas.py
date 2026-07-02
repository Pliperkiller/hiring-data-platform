"""Request / response Pydantic schemas for the ingestion API (docs/API_CONTRACT.md).

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
    model_config = ConfigDict(extra="allow")

    id: Any = None
    department: Any = None


class JobIn(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: Any = None
    job: Any = None


class HireIn(BaseModel):
    model_config = ConfigDict(extra="allow")

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
    load_id: int
    accepted: int
    rejected: int
    rejected_rows: list[RejectedRowOut] = []


class ErrorDetail(BaseModel):
    code: str
    message: str
    detail: dict[str, Any] | None = None


class ErrorBody(BaseModel):
    error: ErrorDetail
