"""Forward-only SQL migrations from `sahayak.store.migrations`, tracked in schema_migrations.

`migrate(conn)` applies pending `*.sql` in name order. Filenames containing `bm25` are skipped
when `pg_search` is unavailable (Neon). Always `commit()` after the pending-list SELECT so
nested transactions are real commits, not savepoints.
"""

from importlib.resources import files

import psycopg
import structlog

log = structlog.get_logger()
OPTIONAL_PREFIX = "bm25"  # migrations whose name contains this need the pg_search extension


def has_extension(conn: psycopg.Connection, name: str) -> bool:
    row = conn.execute("SELECT 1 FROM pg_available_extensions WHERE name = %s", (name,)).fetchone()
    return row is not None


def migrate(conn: psycopg.Connection) -> list[str]:
    """Apply pending migrations in one transaction each. Returns the names applied."""
    conn.execute(
        "CREATE TABLE IF NOT EXISTS schema_migrations "
        "(name text PRIMARY KEY, applied_at timestamptz NOT NULL DEFAULT now())"
    )
    conn.commit()
    done = {r[0] for r in conn.execute("SELECT name FROM schema_migrations").fetchall()}
    # Commit the SELECT's implicit transaction so the blocks below are real COMMITs,
    # not savepoints that vanish when the connection closes.
    conn.commit()
    scripts = sorted(
        (p for p in files("sahayak.store.migrations").iterdir() if p.name.endswith(".sql")),
        key=lambda p: p.name,
    )
    applied: list[str] = []
    for script in scripts:
        if script.name in done:
            continue
        if OPTIONAL_PREFIX in script.name and not has_extension(conn, "pg_search"):
            log.info("migration_skipped_no_pg_search", name=script.name)
            continue
        with conn.transaction():
            conn.execute(script.read_text(encoding="utf-8"))  # type: ignore[arg-type]
            conn.execute("INSERT INTO schema_migrations (name) VALUES (%s)", (script.name,))
        applied.append(script.name)
    return applied
