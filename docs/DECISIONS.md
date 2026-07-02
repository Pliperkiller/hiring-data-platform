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

## Historical load UI (Phase 4)

- **Three separate `st.file_uploader` widgets, not one multi-file uploader.** The CSVs are
  headerless and carry no metadata identifying which table they belong to; explicit
  per-table uploaders (labeled "departments.csv", "jobs.csv", "hired_employees.csv") are
  simpler and more robust than filename-sniffing or column-count heuristics, and match how
  the challenge ships three separate files.
- **Rejected rows are disambiguated with `table` + `batch_index` + `row_index`.** The API's
  `row_index` is only unique within one batch's response; running three tables across many
  batches needs `table` (which table) and `batch_index` (0-based, per-table batch sequence
  number) alongside it so the combined summary table never conflates row 0 of hires batch 2
  with row 0 of departments batch 0.
- **A failed batch (network error, unexpected status) is recorded and skipped, not fatal.**
  `run_historical_load` continues with the next batch of the same table, and subsequent
  tables, rather than aborting the whole run. A `departments`/`jobs` batch failure is
  surfaced with an explicit UI warning, since it can cause a wave of
  `UNKNOWN_DEPARTMENT`/`UNKNOWN_JOB` rejections in `hired_employees` that are a downstream
  consequence, not a data problem in the hire rows themselves.
- **Known limitation: the `ui` service's `depends_on: app` is start-order only, not a
  readiness gate.** `app` has no healthcheck today, and adding a full healthcheck-gated
  dependency is out of scope for this phase. If a user clicks "Run historical load" before
  the API is actually accepting connections, `post_fn` turns the connection error into a
  failed `BatchOutcome` (readable message in the failed-batches table) instead of hanging
  or showing a raw traceback — the fix is simply to retry once the API is up.
- **CSVs are decoded as ASCII, matching `docs/DATA_MODEL.md`'s documented encoding for the
  real challenge files.** A decode failure (e.g. an unexpected non-ASCII upload) is caught
  and shown as a clear per-file `st.error`, not an unhandled exception.
- **`app/application/load_historical.py` was removed rather than implemented.** Option B
  (the Streamlit HTTP client, decided above) means there is no backend use case for
  historical load — the UI repeatedly calls the existing `IngestBatch`-backed endpoints
  exactly as any other API client would. `docs/DESIGN.md`'s folder-layout tree is updated
  to match.
- **`MAX_BATCH_SIZE` lives in `app/interface/ingest_constants.py`**, a tiny constant-only
  module sibling to both `api/` and `ui/` under `interface/`. `api/schemas.py` and
  `ui/historical_load.py` both import it, so the 1000-row cap is defined once. It does not
  live inside `api/schemas.py` itself because that would force the UI (a thin HTTP client)
  to import Pydantic/FastAPI-coupled code just for an integer constant.
- **`app/interface/ui/streamlit_app.py` is excluded from the coverage measurement**
  (`[tool.coverage.run].omit` in `pyproject.toml`). All of its logic worth testing —
  chunking, ordering, aggregation, CSV parsing, failure handling — lives in
  `historical_load.py`, which is unit-tested near 100%. `streamlit_app.py` itself is thin
  widget/session_state glue; testing it would mean driving Streamlit's rendering internals
  for no correctness benefit, which is exactly the kind of coverage-inflation this project
  avoids.

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
- **Refresh lives behind a new `ReportRepository`, injected into `IngestBatch`.** A domain
  `ReportRepository` interface exposes `refresh_views()` alongside the two read methods, and is
  injected into `IngestBatch` the same way the other six repositories are (a 7th constructor
  param). This keeps the use case free of SQLAlchemy imports and mirrors the existing
  constructor-injection pattern, instead of reaching into
  `app/infrastructure/db/repositories.py` from the application layer.
- **`REFRESH MATERIALIZED VIEW`, not `CONCURRENTLY`.** `CONCURRENTLY` requires a unique index on
  the view and only pays off when readers must never block during a long refresh; this
  project's data volume and single-droplet beta deployment don't need it. A brief read-lock on
  the view during refresh is an acceptable trade-off here.
- **Refresh commits separately from the batch, after it, and never fails the batch.** In
  `IngestBatch._run_batch`, the batch's own commit happens first; refresh then runs in a
  `try/except` that commits again on success or rolls back and logs a warning on failure —
  never re-raising. Running refresh inside the batch's own transaction was rejected: a refresh
  failure would abort that whole Postgres transaction and roll back already-valid accepted
  rows, letting an unrelated reporting concern compromise the CLAUDE.md-mandated ingestion
  guarantees. A stale report is recoverable; lost ingestion data is not.
- **Report rows are frozen dataclasses (`HireByQuarterRow`, `DepartmentAboveAverageRow`), not
  dicts.** Matches the Phase 1-4 convention of typed domain entities everywhere; costs nothing
  extra since the fields map 1:1 to the view columns.
- **Materialized views remain excluded from backup/restore.** Confirmed against
  `docs/BACKUP_RESTORE.md`'s six-table list: the two report views are derived data, rebuilt by
  `REFRESH` from the six backed-up tables, so backing them up independently would be redundant.

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
- **AVRO schemas are Python dict literals, not `.avsc` files** (`app/infrastructure/avro/
  schemas.py`). They mirror the SQLAlchemy models the way the models already mirror
  `DATA_MODEL.md` — code, not an external schema file — and this project only uses external
  files (`sql/*.sql`) where there's no natural Python representation, which doesn't apply
  here. A dict literal is also what `fastavro.writer`/`reader` accept directly, with no
  file-loading indirection, and gets real mypy/ruff coverage that a `.avsc` file would not.
- **Backup and restore CLIs are strictly single-table**, matching `python -m
  app.application.backup/restore <table>` — no "all tables" mode. An operator backs up or
  restores everything by invoking the command six times in the documented order.
- **`TRUNCATE TABLE <name> CASCADE`, uniformly on all six tables.** Because restore is
  single-table per invocation, an operator can legally restore `departments` alone while
  `employees` still references old rows; a plain `TRUNCATE` would fail with a foreign-key
  error. `CASCADE` is what makes the single-table contract work in isolation for every table,
  not just a convenience for the ones that structurally need it.
- **Identity-PK tables (`employee_versions`, `loads`, `rejected_records`) restore via raw
  `OVERRIDING SYSTEM VALUE` inserts plus an explicit sequence resync.** Verified empirically:
  SQLAlchemy's Postgres dialect never emits `OVERRIDING SYSTEM VALUE` itself — both ORM and
  Core inserts raise `psycopg.errors.GeneratedAlways` when given an explicit id against a
  `GENERATED ALWAYS AS IDENTITY` column. A raw `text()` executemany `INSERT ... OVERRIDING
  SYSTEM VALUE` is the fix, added as a `restore_all()` method per repository. This alone
  leaves the underlying sequence un-advanced, so every identity-table restore ends with
  `setval(pg_get_serial_sequence(...), MAX(id)+1, false)` to prevent a subsequent normal
  insert from colliding with a restored id. The other three tables (natural business-key
  PKs) restore through their existing `upsert()`/`add()` methods unchanged.
- **Backup/restore are exposed via `POST /admin/backup/{table}` and `POST
  /admin/restore/{table}`, reversing the earlier "not HTTP endpoints" decision above.** The
  Streamlit UI gained a "Backup & Restore" tab so an operator can trigger these without a
  shell into the app container; the admin endpoints and the CLI call the identical `Backup`/
  `Restore` use cases, so there is exactly one implementation either way. This is a
  deliberate trade-off, not an oversight: this project has no user/role access control
  anywhere (`ROADMAP.md`'s out-of-scope list), so `/admin/*` has no authentication of its
  own, and `POST /admin/restore/{table}` is destructive and reachable by anyone who can reach
  the API. The Streamlit tab requires a per-table confirmation checkbox before enabling its
  restore button as a UI-level safeguard, but the real mitigation has to be operational: a
  production deployment must restrict `/admin/*` at the network/reverse-proxy level (not
  exposed through the public gateway, or IP-gated), which is outside this repo's scope.
- **`data/` backup files are not bind-mounted from the app container to the host.** Deferred
  as an operations follow-up; a durable volume mount is a one-line `docker-compose.yml`
  change but is out of this phase's scope (implementing correct commands, not deployment
  durability).

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
