"""Shared constants for the ingestion HTTP boundary (API schemas + UI client).

Lives directly under app/interface/, not inside api/, so the Streamlit UI (a thin HTTP
client, sibling to the api package) can import this single constant without importing
api/schemas.py or anything else FastAPI/Pydantic-specific.
"""

from __future__ import annotations

MAX_BATCH_SIZE: int = 1000
MIN_BATCH_SIZE: int = 1
