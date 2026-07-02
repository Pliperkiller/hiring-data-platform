"""CLI adapter for the Restore use case: `python -m app.interface.cli.restore <table>`."""

from __future__ import annotations

import sys

from app.domain.backup_codec import TABLE_NAMES, validate_table_name
from app.interface.composition import build_restore


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(
            f"usage: python -m app.interface.cli.restore <table>\n"
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
        count = build_restore(session).run(table)
        print(f"restored {table}: {count} row(s)")
        return 0
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
