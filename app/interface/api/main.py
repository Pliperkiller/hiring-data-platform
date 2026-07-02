from fastapi import FastAPI

from app.infrastructure.logging_config import configure_logging
from app.interface.api.errors import register_exception_handlers
from app.interface.api.routers import admin, ingest, reports

configure_logging()

app = FastAPI(
    title="Hiring Data Platform API",
    description=(
        "Ingests hiring records, validates them, keeps a versioned (SCD Type 2) history, "
        "exposes two BI reports, and supports AVRO backup/restore. See "
        "docs/API_CONTRACT.md for the full contract."
    ),
    version="1.0.0",
)
register_exception_handlers(app)
app.include_router(ingest.router)
app.include_router(reports.router)
app.include_router(admin.router)


@app.get("/health", summary="Liveness check", description="Returns 200 once the app is up.")
def health() -> dict[str, str]:
    return {"status": "ok"}
