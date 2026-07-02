# Decisions

Closed design decisions with rationale. This is what stops the agent from re-deciding
settled questions or repeating past mistakes. Most were resolved against the real source
data; a few were product decisions from requirements.

## Stack and deployment

- **Language / stack: Python (FastAPI) + PostgreSQL.** One engine covers the transactional
  writes (validation, versioning, rejected log) and the analytical reads (marts). Self-hosts
  on the droplet. If analytics later outgrows it, export the mart layer to a columnar store
  without touching ingestion.
- **Deployment: Option C beta on a self-managed droplet.** Deployed and accessible, but the
  database is self-hosted on the existing DigitalOcean droplet, not a managed service.

## Validation and rejection

- **Hybrid validation.** Schema, ISO 8601 format, and types validated in the app (Pydantic +
  domain service); referential integrity (FK existence) enforced by the database as a safety
  net, with an app-side check for friendly errors.
- **Reject and log, never coerce.** Invalid rows are not inserted; they go to
  `rejected_records`. A prior version coerced empties into sentinels and inserted them; that
  is explicitly forbidden.
- **Field-level reason.** Each rejected record names the field that failed plus a reason
  code, so whoever fixes the data knows exactly what to correct.
- **Strict everywhere the data allows it for free.** The source data has no type coercion
  cases, no bad datetimes, and no duplicate ids; ids are all positive. So we take the strict
  stance (exact ISO 8601 with `Z`, integer ids, etc.) at no cost, because no legitimate row is
  affected.
- **Partial success, per row.** A batch with some invalid rows inserts the valid ones and
  rejects the rest; one bad row does not sink the batch. (70 of 1999 rows are invalid, spread
  out, so atomic rejection would be wrong.)
- **`ReasonCode` is a `StrEnum`.** Chosen over frozen-dataclass sentinel constants because a
  `StrEnum` member is simultaneously a `str` — it drops into `rejected_records.reason_code
  TEXT` and JSON responses with no adapter code — while still being closed and exhaustive (a
  new code requires a deliberate enum edit, not just any string).
- **Wrong-typed id/FK values collapse into the existing `MISSING_*` code, not a new code.** A
  string-digit id (`"5"`), a `bool` id, or a non-integer `department_id`/`job_id` are treated
  identically to an absent value — the catalog's own meaning column ("id empty or not an
  integer") already covers this, and inventing a new code would break the closed catalog.
  FK-existence checks (`UNKNOWN_DEPARTMENT`/`UNKNOWN_JOB`) only run once the type check passes.
  Positivity is deliberately **not** checked: `0` and negative ints pass, since the catalog's
  meaning column has no positivity clause and the DDL has no `CHECK` constraint for it.
  Duplicate ids are also out of scope for field-level validation — detecting one needs
  cross-row/DB state (`EmployeeRepository.exists()`), which belongs to Phase 3's SCD-transition
  logic, not a single row validated in isolation.
- **Whitespace-only strings count as empty for `MISSING_NAME`.** `"   "` fails the same way as
  `""` or a missing key — decorative whitespace isn't a legitimate name.
- **Validation aggregates every field-level defect per row; no fail-fast.** A row can fail more
  than one field simultaneously (e.g. an unknown department and an unknown job at once); the
  validation service collects every `FieldError` before returning, rather than stopping at the
  first one. `rejected_records` stores one `field`/`reason_code` per row, so a multi-defect row
  may become more than one `rejected_records` row for the same `raw_payload` — that split is
  Phase 3's concern, not this domain service's.
- **No generic `Result[T, E]` wrapper for validation outcomes.** The validation service returns
  plain unions (e.g. `Department | ValidationFailure`), discriminated by `isinstance` — no
  Result/Either library is a dependency, and there is no second consumer that would justify a
  hand-rolled generic wrapper.

## Ingestion

- **Batch 1–1000 is an input limit, not an internal chunking rule.** The API caps each
  request body at 1000 rows and rejects larger ones with 422. The client splits large inputs
  into multiple requests. (A prior version misread this: it chunked an arbitrary file into
  1000-row inserts, which is a different thing.)
- **Synchronous, no queues.** Ingestion is on-demand batch; no streaming, no background job
  system. Progress for the historical load is shown client-side (the UI counts its own
  requests).
- **Historical load reuses the same validation core.** The source CSV contains intentionally
  invalid rows, so a blind bulk/COPY path would insert garbage. The historical load goes
  through the same validation and rejection as the API.
- **Historical load via the Streamlit client (Option B).** The UI reads the CSVs, chunks into
  1000s, and POSTs to the existing endpoints in dependency order. (The challenge document
  leaves the historical-load strategy open, so this is a choice, not a requirement. For the
  production vision a separate bulk job, Option A, would be preferred.)
- **`IngestBatch` is one class with three thin methods, not three classes.** The "one endpoint
  per table" decision above is scoped to routes/schemas ("each table has a distinct schema");
  the three tables share all the batch-orchestration machinery (one `Load` per call, `row_index`
  tracking, fanning a `ValidationFailure` into `RejectedRecord` rows, `mark_finished`, the single
  commit). Only "how to persist one valid row" differs per table (upsert vs. SCD decide-and-
  execute), so it factors into a small per-table callback into one shared batch loop instead of
  triplicating the shared machinery across three classes.
- **One `session.commit()` per batch, at the end.** Repositories `flush()` only (see below);
  `IngestBatch` owns the transaction boundary and commits once after all rows are processed and
  `Load.mark_finished` is called. Rows are capped at 1000 and ingestion is synchronous with no
  queues, so one transaction per batch is well within Postgres's comfort zone, and it keeps the
  `Load`'s final counts, every persisted row, and every `RejectedRecord` atomically visible
  together. An unhandled infrastructure error mid-batch is not caught locally — it propagates to
  a 500 and the whole batch rolls back, so a 500 response never coexists with partial writes a
  client was told didn't happen.
- **`rejected` in the ingestion response counts rows, not field-errors.** A row with two
  simultaneous defects (e.g. unknown department and unknown job) contributes 1 to `rejected` but
  2 entries to `rejected_rows`, both sharing that row's `row_index`. `API_CONTRACT.md`'s
  worked example doesn't disambiguate this directly, but "accepted + rejected = rows submitted"
  and the row-level language throughout the contract ("invalid rows are not [persisted]") both
  point to row-counting; the earlier "that split is Phase 3's concern" note in the Validation
  section is resolved here.
- **Materialized-view refresh is out of scope for Phase 3.** `DATA_MODEL.md` says to "refresh
  both [report views] at the end of each ingestion load," but the views themselves don't exist
  until Phase 5 (`feature/reports`) creates them. `IngestBatch` in this phase does not call,
  stub, or guard a refresh — no speculative plumbing for a feature two phases away. Phase 5
  wires the refresh into `IngestBatch` once the views exist, as a small follow-up change to this
  same use case.
- **`BATCH_TOO_LARGE` is a distinct error code**, detected from the Pydantic length-violation
  error on the batch body (a `too_long`/`too_short` error type on the list field) and returned
  as `code: "BATCH_TOO_LARGE"` with `detail: {"received": N, "max"/"min": ...}`, matching
  `API_CONTRACT.md`'s worked example and its own dedicated row in the status-code table for
  "a batch with 0 or more than 1000 rows." Every other malformed-request 422 (wrong envelope
  shape, non-object array elements) stays the generic `code: "VALIDATION_ERROR"`.

## History (SCD Type 2)

- **SCD Type 2 for traceability.** Employee attribute changes are versioned, not overwritten,
  to feed the analytics warehouse with full history.
- **Tracked attributes: name, department, job.** A change in any of these opens a new version.
- **Hires counted once, at the hire-time department/job.** A transfer creates a version but
  must not move the historical hire between departments. Reports read the immutable hire
  facts, not the versions.
- **Re-upload semantics.** Same employee with identical attributes = no-op; with changed
  attributes = new version; only structurally broken rows are rejected. (This supersedes an
  earlier "duplicate = reject" idea.)

## Reports

- **Year filter is mandatory and explicit.** Reports consider only 2021. The data contains
  286 valid 2022 rows; without the filter they inflate the results. This was the exact bug in
  a prior version's second query, which compared an all-time count against a 2021 average.
- **"Valid records only" is guaranteed by construction.** Because rejection is hard, invalid
  rows never enter the tables, so no extra "valid" filter is needed in the queries. The year
  filter is separate and still required.
- **Quarterly pivot via `SUM(CASE WHEN ...)`.** Portable and readable; avoids the proprietary
  `PIVOT` operator (which Postgres lacks anyway).
- **Report 1 shows only combinations with at least one hire.** The full department x job
  cross-product would be ~2200 rows, almost all zeros. Zeros within a shown row are fine
  (a quarter with no hires for a combo that did hire that year).
- **Report 2 average is over departments that hired in the period.** Avoids dormant
  departments dragging the baseline down. With the current data all 12 departments hired, so
  this equals the average over all departments.
- **Quarter bucketing in UTC.** Set the database timezone to UTC so `EXTRACT(QUARTER ...)` is
  deterministic across environments.

Verified numbers against the source data: report 1 yields 933 combinations, quarter columns
summing to 1643 (total valid 2021 hires); report 2 yields 7 departments above the average of
137 (Support 216, Engineering 205, Human Resources 201, Services 200, Business Development
185, Research and Development 148, Marketing 142).

## Backup and restore

- **Backup includes everything, including `rejected_records`.** A full, faithful copy.
- **Backup format: AVRO** on the filesystem, one file per table. AVRO carries its schema
  inside the file, so backups are self-describing.
- **Restore = full replace** (truncate + insert), leaving the table identical to the backup,
  never merging. Restore respects reference order (catalogs first).
- **Backup/restore are admin commands, not public endpoints.** Restore is destructive.

## Miscellaneous

- **Primary key for employees is the source `id`.** No surrogate for the business key. This
  also gives idempotency for free at the fact level (re-inserting the same id hits the PK).
- **Load order.** Reference tables (`departments`, `jobs`) load before `hired_employees`,
  because employee FKs reference them.

## Schema and persistence (Phase 1)

- **Migrations run via the container entrypoint, not a FastAPI startup hook.**
  `docker-entrypoint.sh` runs `alembic upgrade head` before `exec`-ing uvicorn. An in-app
  startup hook would run once per worker process, racing (Alembic's own version-locking
  makes this safe, but wasteful and noisy) — the entrypoint runs it exactly once per
  container start, before the app accepts traffic.
- **Repositories `flush()`, never `commit()`.** The caller (a test fixture today, a use case
  in later phases) owns the transaction boundary, so a batch-ingestion use case can commit or
  roll back the whole operation atomically once repositories exist.
- **`Load` is co-located with `RejectedRecord`** in `app/domain/rejected_record.py` rather
  than a separate `load.py`. `DESIGN.md`'s folder layout does not reserve a slot for it, and
  the two are relationally coupled (`rejected_records.load_id -> loads.id`), both populated
  during ingestion/rejection.
- **`app/infrastructure/db/session.py` is a small, deliberate addition** to `DESIGN.md`'s
  folder layout: something has to own `Engine`/`sessionmaker` construction so Alembic's
  `env.py`, repositories, and tests can all get a `Session` from the same place.
