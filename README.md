# Hiring Data Platform

A data platform that ingests hiring records - an initial historical load plus ongoing
uploads - validates them, keeps a versioned history (SCD Type 2) for analytics, exposes two
BI reports, and supports AVRO backup/restore. Deployed as a beta on a self-managed
DigitalOcean droplet.

Built with Python, FastAPI, PostgreSQL, SQLAlchemy + Alembic, a Streamlit UI, fastavro,
Docker Compose, pytest, and GitHub Actions. See `CLAUDE.md` for the full architecture map
(DDD layering: domain / application / infrastructure / interface) and the non-negotiable
project rules (never coerce invalid data, reports always filter to 2021, restore is always
a full replace, synchronous batch ingestion only).

## Live deployment (beta)

Running on a DigitalOcean droplet:

- API: `http://142.93.55.58:8000` - Swagger UI at `http://142.93.55.58:8000/docs`
- Streamlit UI: `http://142.93.55.58:8501`

This is a beta over plain HTTP - no TLS yet (see `docs/DECISIONS.md`'s Phase 7 entry on the
deferred network-level `/admin/*` restriction). The Admin tab is password-gated, but
`/admin/*` itself has no authentication of its own at the network level - treat this address
as not hardened for untrusted traffic.

## Quickstart

```bash
cp .env.example .env
docker compose up -d --build
```

This starts three services:

- **`db`** - PostgreSQL, bound to `127.0.0.1` only.
- **`app`** - the FastAPI service, on `http://localhost:8000`. Interactive API docs at
  [`/docs`](http://localhost:8000/docs) (Swagger UI) and `/redoc`; liveness at `GET /health`.
- **`ui`** - the Streamlit app, on `http://localhost:8501`, with two tabs: **Historical
  Load** (upload the three source CSVs) and **Admin** (backup/restore/reset - see below).

Migrations run automatically on container startup (`docker-entrypoint.sh` runs
`alembic upgrade head` before the app starts).

## Admin tab

The Streamlit **Admin** tab is password-gated: set `ADMIN_PASSWORD` in `.env` (see
`.env.example`) before deploying. This is a UI-layer safeguard only - see
`docs/DECISIONS.md` and `docs/API_CONTRACT.md` for why the underlying `/admin/*` HTTP
endpoints have no authentication of their own. Inside the tab:

- **Backup / Restore**, per table, with a confirmation checkbox before restore (destructive:
  full replace via truncate + insert).
- **Reset database**, which truncates all six tables and refreshes both report views. It
  never touches existing `data/*.avro` backups. It requires typing the exact string `RESET`
  into a text input before the button enables - this is the single most destructive action
  in the app.

## Backup and restore via CLI

The same use cases the Admin tab calls over HTTP are also available as CLI commands, for
direct operator use inside the app container:

```bash
docker compose exec app python -m app.interface.cli.backup <table>
docker compose exec app python -m app.interface.cli.restore <table>
```

`<table>` is one of `departments`, `jobs`, `employees`, `employee_versions`, `loads`,
`rejected_records`. See `docs/BACKUP_RESTORE.md` for the full specification, including
restore ordering and AVRO type notes.

## Documentation

Start with `CLAUDE.md` for the project map. Detailed specs live in `docs/`:

- `docs/DESIGN.md` - architecture, ingestion flow, deployment
- `docs/DATA_MODEL.md` - tables, columns, SCD structure, reason codes, indexes
- `docs/API_CONTRACT.md` - endpoints, request/response schemas, status codes, error body
- `docs/DECISIONS.md` - closed design decisions with rationale
- `docs/ROADMAP.md` - phases/branches, CI/CD, per-phase definition of done
- `docs/BACKUP_RESTORE.md` - AVRO backup/restore specification

## Development

Trunk-based flow (GitHub Flow): `feature/<name>` or `fix/<name>` branch → PR → CI green
(lint, types, tests, coverage ≥ 90%) → merge to `main` → auto-deploy to the droplet. All
code, comments, commit messages, and docs are in English; commits follow Conventional
Commits (`feat(scope): ...`, `fix(scope): ...`, `test: ...`, `docs: ...`, `chore: ...`,
`ci: ...`). See `docs/ROADMAP.md` for the full phase-by-phase plan.

```bash
pytest --cov=app --cov-fail-under=90   # tests + coverage gate
ruff check .                           # lint
mypy app                               # type check
alembic revision --autogenerate -m "message"   # new migration
```
