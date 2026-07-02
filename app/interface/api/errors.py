"""Exception handlers mapping errors to the structured error body (docs/API_CONTRACT.md).

Two handlers: RequestValidationError (422) and a catch-all Exception (500), both consistently
producing the {"error": {"code","message","detail"}} shape. Logging uses Python's stdlib
`logging` module via a plain module-level logger; level and format are configured once, at API
startup, by app.infrastructure.logging_config.configure_logging() — this module doesn't own any
logging setup itself, just its own logger.exception() call below.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)

_LENGTH_VIOLATION_TYPES = {"too_long", "too_short"}


def _batch_too_large_detail(exc: RequestValidationError) -> dict[str, Any] | None:
    """If exc is a batch-length violation (0 or >1000 rows), return {received, max/min}."""
    for error in exc.errors():
        if error["type"] not in _LENGTH_VIOLATION_TYPES:
            continue
        ctx = error.get("ctx", {})
        detail: dict[str, Any] = {"received": ctx.get("actual_length")}
        if error["type"] == "too_long":
            detail["max"] = ctx.get("max_length")
        else:
            detail["min"] = ctx.get("min_length")
        return detail
    return None


async def validation_error_handler(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, RequestValidationError)
    batch_detail = _batch_too_large_detail(exc)
    if batch_detail is not None:
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "BATCH_TOO_LARGE",
                    "message": "Batch exceeds the 1000-row limit"
                    if "max" in batch_detail
                    else "Batch is below the 1-row minimum",
                    "detail": batch_detail,
                }
            },
        )
    return JSONResponse(
        status_code=422,
        content={
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "Request body failed validation",
                "detail": {"errors": exc.errors()},
            }
        },
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled error processing %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "INTERNAL_ERROR",
                "message": "An unexpected error occurred",
                "detail": None,
            }
        },
    )


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(RequestValidationError, validation_error_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)
