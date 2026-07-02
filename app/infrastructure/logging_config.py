"""One-shot root logger configuration, applied at API startup.

Every module already does `logging.getLogger(__name__)`; this just gives the root logger a
consistent level and format instead of relying on stdlib defaults, per docs/ROADMAP.md's Phase 7
observability goal. Level is configurable via the LOG_LEVEL environment variable.
"""

from __future__ import annotations

import logging
import os


def configure_logging() -> None:
    logging.basicConfig(
        level=os.environ.get("LOG_LEVEL", "INFO"),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


__all__ = ["configure_logging"]
