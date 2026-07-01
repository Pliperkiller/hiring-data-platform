# Hiring Data Platform

Ingests hiring records, validates them, keeps a versioned history (SCD Type 2) for
analytics, exposes two BI reports, and supports AVRO backup/restore. Beta deployment on a
DigitalOcean droplet.

## Quickstart

```bash
docker compose up -d --build
```

- API: FastAPI service (see `docs/API_CONTRACT.md`)
- UI: Streamlit app for the historical load and dashboards
- Health check: `GET /health`

## Documentation

Start with `CLAUDE.md` for the project map. Detailed specs live in `docs/`:

- `docs/DESIGN.md` — architecture and flows
- `docs/DATA_MODEL.md` — database schema and SCD model
- `docs/API_CONTRACT.md` — API endpoints and contracts
- `docs/DECISIONS.md` — design decisions and rationale
- `docs/ROADMAP.md` — build plan by phase
- `docs/BACKUP_RESTORE.md` — backup/restore specification

## Development

Trunk-based flow: branch → PR → CI (tests, coverage ≥ 90%) → merge to `main` → auto-deploy.
All code, commits, and docs are in English. See `docs/ROADMAP.md`.
