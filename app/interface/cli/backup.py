"""CLI adapter for the Backup use case: `python -m app.interface.cli.backup <table>`."""

from __future__ import annotations

import sys

from app.domain.backup_codec import TABLE_NAMES, validate_table_name
from app.interface.composition import build_backup


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(
            f"usage: python -m app.interface.cli.backup <table>\n"
            f"  tables: {', '.join(TABLE_NAMES)}",
            file=sys.stderr,
        )
        return 2
    table = argv[1]
    try:
        validate_table_name(table)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    from app.infrastructure.config import get_settings
    from app.infrastructure.db.session import build_engine, build_sessionmaker

    engine = build_engine(get_settings().database_url)
    session = build_sessionmaker(engine)()
    try:
        path = build_backup(session).run(table)
        print(f"backed up {table} -> {path}")
        return 0
    finally:
        session.close()


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
