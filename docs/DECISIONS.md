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
  cases, no bad datetimes, no 0/negative/duplicate ids. So we take the strict stance (exact
  ISO 8601 with `Z`, integer ids, etc.) at no cost, because no legitimate row is affected.
- **Partial success, per row.** A batch with some invalid rows inserts the valid ones and
  rejects the rest; one bad row does not sink the batch. (70 of 1999 rows are invalid, spread
  out, so atomic rejection would be wrong.)

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
