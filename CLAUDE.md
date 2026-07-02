# CLAUDE.md

Project context for Claude Code. Keep this file short and high-signal; detailed specs live
in `docs/`.

## What this is

A data platform that ingests hiring records (an initial historical load plus ongoing
uploads), validates them, keeps a versioned history (SCD Type 2) for analytics, exposes two
BI reports, and supports AVRO backup/restore. Deployed as a beta on a self-managed
DigitalOcean droplet.

## Stack

Python · FastAPI · PostgreSQL · SQLAlchemy + Alembic · Streamlit (UI) · fastavro ·
Docker Compose · pytest · GitHub Actions.

## Architecture (DDD, dependencies point inward)

- `app/domain/` — pure domain: entities, value objects, domain services, repository
  interfaces. No framework or DB imports here.
- `app/application/` — use cases orchestrating domain + repositories.
- `app/infrastructure/` — SQLAlchemy models, `db/session.py` (engine/session construction),
  repository implementations, Alembic migrations, AVRO, config.
- `app/interface/` — FastAPI routers/schemas/error handlers, and the Streamlit UI.
- `tests/` — `unit/` (domain + application, no DB) and `integration/` (repositories, API via
  TestClient, AVRO round-trip).

Full layout and diagrams in `docs/DESIGN.md`.

## Non-negotiable rules (these encode past mistakes; do not break them)

- **Never coerce invalid data.** Invalid records are rejected and logged, never silently
  transformed or inserted. Rejection reasons are recorded at field level (which field failed
  plus a reason code). A prior version coerced empties into sentinels and inserted garbage;
  do not repeat that.
- **Reports always filter to year 2021.** The dataset contains 2022 records; omitting the
  year filter inflates results. This exact omission was a real bug in a prior version.
- **Restore = full replace** (truncate + insert, reference tables first), never a merge.
- **SCD Type 2:** an employee attribute change creates a new version; hires are counted once
  and attributed to the hire-time department/job, not the current one. `employees` carries
  both: immutable hire facts (`hire_department_id`/`hire_job_id`, used by reports) and current
  state (`department_id`/`job_id`, kept in sync with `employee_versions` on every change).
- **Do not over-engineer.** Ingestion is synchronous batch (1–1000 rows per request). No
  queues, no streaming, no background job system.

## Conventions

- All code, comments, docstrings, commit messages, and repo docs in **English**.
- Commits: Conventional Commits (`feat(scope): ...`, `fix(scope): ...`, `test: ...`,
  `docs: ...`, `chore: ...`, `ci: ...`).
- Branches: `feature/<name>`, `fix/<name>`. Trunk-based flow: PR → CI green → merge to
  `main` → auto-deploy to the droplet.
- Tests are required in the same branch as the feature; coverage ≥ 90% measured on `app`.
- Error handling: domain exceptions are mapped to HTTP responses via FastAPI handlers;
  responses use a structured error body, never a raw stack trace.

## Commands (fill in / confirm as the project is built)

- Run locally: `docker compose up -d --build`
- Tests + coverage gate: `pytest --cov=app --cov-fail-under=90`
- Lint / types: `ruff check .` · `mypy app`
- Migrations: `alembic upgrade head` · `alembic revision --autogenerate -m "message"`.
  `docker-entrypoint.sh` runs `alembic upgrade head` automatically before the app starts, in
  every environment (local Docker, CI, droplet).
- Deploy: merge to `main` (GitHub Actions runs the droplet deploy)

## Ubiquitous language (use these exact terms in code)

**employee**, **version** (an SCD row), **hire**, **hire-time department/job**, **current
department/job**, **reference table** (department, job), **rejected record**, **reason
code**, **load** (one ingestion run), **batch** (the rows in one request).

## Documents

- `docs/DESIGN.md` — architecture, ingestion flow, deployment
- `docs/DATA_MODEL.md` — tables, columns, SCD structure, reason codes, indexes (build
  SQLAlchemy models and Alembic migrations from this)
- `docs/API_CONTRACT.md` — endpoints, request/response schemas, status codes, error body
- `docs/DECISIONS.md` — closed design decisions with rationale
- `docs/ROADMAP.md` — phases/branches, CI/CD, per-phase definition of done
- `docs/BACKUP_RESTORE.md` — AVRO backup/restore specification
- `sql/` — the two report queries, already verified against the source data
