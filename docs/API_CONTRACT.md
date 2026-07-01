# API Contract

FastAPI service. One ingestion endpoint per table (each table has a distinct schema, so this
keeps validation and the contract explicit). Reports are read endpoints. All request and
response bodies are JSON.

## Endpoints

| Method | Path | Purpose |
|---|---|---|
| POST | `/ingest/departments` | ingest a batch of departments (upsert by id) |
| POST | `/ingest/jobs` | ingest a batch of jobs (upsert by id) |
| POST | `/ingest/hired_employees` | ingest a batch of hires (applies SCD versioning) |
| GET | `/reports/hires-by-quarter` | report 1 (2021) |
| GET | `/reports/departments-above-average` | report 2 (2021) |
| GET | `/health` | liveness check |

## Ingestion requests

The body is a JSON array of 1 to 1000 objects. The 1000 cap is enforced by the request model
(a list with min length 1, max length 1000); an out-of-range body is rejected with **422**
before any row is processed.

`POST /ingest/departments` and `/ingest/jobs`:

```json
[
  { "id": 1, "department": "Engineering" },
  { "id": 2, "department": "Sales" }
]
```

`POST /ingest/hired_employees`:

```json
[
  { "id": 101, "name": "Ada Lovelace", "datetime": "2021-02-10T09:30:00Z", "department_id": 1, "job_id": 5 },
  { "id": 102, "name": "Grace Hopper", "datetime": "2021-05-22T14:00:00Z", "department_id": 1, "job_id": 5 }
]
```

## Ingestion response (partial success)

Ingestion returns **200** with a summary, even when some rows are rejected. Valid rows are
persisted; invalid rows are not, and are logged to `rejected_records`. A partial load is not
an error.

```json
{
  "load_id": 42,
  "accepted": 950,
  "rejected": 2,
  "rejected_rows": [
    { "row_index": 3, "field": "job_id",   "reason_code": "MISSING_JOB",        "message": "job_id is empty" },
    { "row_index": 7, "field": "department_id", "reason_code": "UNKNOWN_DEPARTMENT", "message": "department_id 999 does not exist" }
  ]
}
```

- `row_index` is 0-based within the submitted batch.
- `field` and `reason_code` match the catalog in `DATA_MODEL.md`.

## Report responses

`GET /reports/hires-by-quarter` returns rows ordered by department then job, only for
combinations with at least one 2021 hire:

```json
[
  { "department": "Accounting", "job": "Actuary", "Q1": 0, "Q2": 1, "Q3": 0, "Q4": 0 },
  { "department": "Engineering", "job": "Software Engineer", "Q1": 3, "Q2": 5, "Q3": 2, "Q4": 4 }
]
```

`GET /reports/departments-above-average` returns departments whose 2021 hires exceed the
average (computed over departments that hired in 2021), ordered by `hired` descending:

```json
[
  { "id": 8, "department": "Support", "hired": 216 },
  { "id": 5, "department": "Engineering", "hired": 205 }
]
```

## Status codes

| Code | When |
|---|---|
| 200 | successful ingestion (including partial success) and successful report reads |
| 422 | malformed request body, or a batch with 0 or more than 1000 rows |
| 500 | infrastructure failure (DB unavailable, etc.) with a controlled body; real detail logged server-side |

Note: there is no per-table 404, because the tables are explicit routes, not a path
parameter.

## Error body

All error responses use a single structured shape, never a raw stack trace:

```json
{
  "error": {
    "code": "BATCH_TOO_LARGE",
    "message": "Batch exceeds the 1000-row limit",
    "detail": { "received": 1500, "max": 1000 }
  }
}
```

`code` is a stable machine-readable string; `message` is human-readable; `detail` is optional
context. Validation failures raised by the request model surface with a `code` of
`VALIDATION_ERROR` and per-field detail.

## Backup and restore

Backup and restore are **not** HTTP endpoints. They are administration commands (restore is
destructive and should only be run by an operator). See `BACKUP_RESTORE.md`.
