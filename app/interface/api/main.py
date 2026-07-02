from fastapi import FastAPI

from app.interface.api.errors import register_exception_handlers
from app.interface.api.routers import admin, ingest, reports

app = FastAPI(title="Hiring Data Platform API")
register_exception_handlers(app)
app.include_router(ingest.router)
app.include_router(reports.router)
app.include_router(admin.router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
