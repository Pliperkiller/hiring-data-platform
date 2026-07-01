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

A reference implementation of the AVRO write/read and the DB round-trip exists in the
standalone AVRO lab produced earlier; adapt it to the real tables and the admin-command
entry points.
