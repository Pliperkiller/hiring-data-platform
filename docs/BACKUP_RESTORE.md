# Backup and Restore

Specification for the AVRO backup and restore features. Implemented as administration
commands, not HTTP endpoints (restore is destructive). Use `fastavro`.

## Why AVRO

AVRO is a binary, schema-carrying format: the schema is stored inside each `.avro` file, so a
backup is self-describing and restores without external metadata. It is compact and its types
are explicit.

## Backup

Export every table to a `.avro` file on the filesystem, one file per table, including
`rejected_records` (backups are full and faithful).

Tables to back up: `departments`, `jobs`, `employees`, `employee_versions`, `loads`,
`rejected_records`.

Per-table AVRO schemas mirror `DATA_MODEL.md`. Notes on types:

- Timestamps (`hire_datetime`, `valid_from`, `valid_to`, `first_loaded_at`, `started_at`,
  `finished_at`, `created_at`) use the logical type `timestamp-millis`. Pass timezone-aware
  UTC datetimes.
- Nullable columns (`valid_to`, `finished_at`, `load_id`, `field`) are modeled as unions with
  `null` (e.g. `["null", "long"]`) with a default of `null`.
- `raw_payload` (JSONB) is serialized as a JSON string field.

## Restore

Restore a table from its `.avro` file by **full replace**: truncate the table, then insert
the rows from the backup. The restored table is identical to the backup; there is no merge.

Restore respects reference order, the same as loading:

1. `departments`, `jobs`
2. `employees`
3. `employee_versions`, `loads`
4. `rejected_records`

Because the tables have foreign keys, truncating a parent requires handling its children;
restore in the order above (or truncate with cascade and then restore all tables in order).
Restore does not re-validate: a backup is trusted, already-clean data.

## Commands (shape)

```
python -m app.application.backup <table>     # writes data/<table>.avro
python -m app.application.restore <table>    # replaces <table> from data/<table>.avro
```

Implementation lives in `app/infrastructure/avro/` (schemas + `codec.py`'s `write_avro`/
`read_avro`) and `app/application/backup.py` / `restore.py`. Both are also reachable over
HTTP as `POST /admin/backup/{table}` / `POST /admin/restore/{table}` (see `API_CONTRACT.md`
and `DECISIONS.md`), used by the Streamlit "Admin" tab — the CLI and the HTTP routes call the
exact same `Backup`/`Restore` use cases, so behavior is identical either way.

## Notes on precision and identity columns

- `timestamp-millis` truncates to millisecond precision. Postgres `TIMESTAMP(timezone=True)`
  columns store microsecond precision, so a restored timestamp is equal to the original only
  down to the millisecond, not byte-for-byte — a deliberate trade-off of the type this spec
  chose (`timestamp-millis`, not `-micros`), not a bug.
- `employee_versions`, `loads`, and `rejected_records` use Postgres
  `GENERATED ALWAYS AS IDENTITY` primary keys. Postgres rejects a plain `INSERT` with an
  explicit value for such a column, and SQLAlchemy's dialect never adds the
  `OVERRIDING SYSTEM VALUE` clause automatically, so restoring these three tables uses a raw
  `INSERT ... OVERRIDING SYSTEM VALUE` to preserve the original ids (required for
  `rejected_records.load_id` FK correctness and round-trip parity), followed by a
  `setval(pg_get_serial_sequence(...), MAX(id)+1, false)` resync so the next normal insert
  doesn't collide with a restored id.
- `TRUNCATE ... CASCADE` is used uniformly on all six tables, not only where the FK graph
  structurally requires it: since restore is strictly single-table per invocation (no "all
  tables" mode), an operator can legally restore `departments` alone while `employees` still
  references old rows, and a plain `TRUNCATE` would fail with a foreign-key error in that
  case. Restoring a table this way also empties its dependents (e.g. restoring `departments`
  empties `employees` and `employee_versions` too); restoring the full six-table set means
  running the CLI (or the admin endpoints) once per table in the order below so every emptied
  dependent gets its own data back immediately after.
- `data/` is bind-mounted from the host (`./data:/code/data` in `docker-compose.yml`, added in
  Phase 7), so backups survive a container recreate, not just a container restart.
