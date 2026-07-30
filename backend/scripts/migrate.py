"""Apply SQL migrations against DATABASE_URL.

Same code path locally and in production, so a migration that works on a laptop
is the one that runs on Render. Uses psycopg2 (sync) rather than the app's
asyncpg engine: migrations are a one-shot script, and asyncpg cannot execute
multi-statement SQL files in one call.

Usage:
    python scripts/migrate.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import psycopg2

MIGRATIONS_DIR = Path(__file__).resolve().parent.parent / "migrations"


def to_sync_url(url: str) -> str:
    """Convert the app's asyncpg URL to the sync form psycopg2 expects."""
    return url.replace("postgresql+asyncpg://", "postgresql://")


def main() -> int:
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        print("DATABASE_URL is not set", file=sys.stderr)
        return 1

    files = sorted(MIGRATIONS_DIR.glob("*.sql"))
    if not files:
        print(f"no .sql files found in {MIGRATIONS_DIR}", file=sys.stderr)
        return 1

    conn = psycopg2.connect(to_sync_url(database_url))
    try:
        # Every migration is idempotent (CREATE ... IF NOT EXISTS), so
        # re-running is safe and no version table is needed yet. Alembic takes
        # over in Phase 1 — see docs/04_DATABASE_DESIGN.md section 6.1 for the
        # baseline/stamp procedure that must happen first.
        conn.autocommit = False
        with conn.cursor() as cur:
            for path in files:
                print(f"applying {path.name} ...")
                cur.execute(path.read_text())
        conn.commit()
    except Exception as exc:
        conn.rollback()
        print(f"migration failed, rolled back: {exc}", file=sys.stderr)
        return 1
    finally:
        conn.close()

    print(f"applied {len(files)} migration(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
