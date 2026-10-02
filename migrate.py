"""Explicit PostgreSQL migrations; never opens or upgrades the SQLite database.

Usage: set TRACKER_MIGRATION_DATABASE_URL, then run python migrate.py.
Use migration credentials, not the eventual runtime database role.
"""

import hashlib
import os
from pathlib import Path

import psycopg


MIGRATIONS = Path(__file__).resolve().parent / "migrations"


class SchemaMismatch(RuntimeError):
    pass


def _migrations(directory: Path) -> list[tuple[str, str, str]]:
    files = sorted(directory.glob("[0-9][0-9][0-9]_*.sql"))
    if not files or len({path.name[:3] for path in files}) != len(files):
        raise SchemaMismatch("Missing migrations or duplicate migration numbers")
    return [
        (path.name, hashlib.sha256(path.read_bytes()).hexdigest(), path.read_text())
        for path in files
    ]


def _validate(applied, migrations, *, complete: bool) -> None:
    expected = [(name, checksum) for name, checksum, _ in migrations]
    if applied != expected[:len(applied)] or (complete and applied != expected):
        raise SchemaMismatch("Database migrations differ from this code; check migration history")


def migrate(connection: psycopg.Connection, directory: Path = MIGRATIONS) -> None:
    """Apply pending migrations atomically, serialized against other deploys."""
    migrations = _migrations(directory)
    with connection.transaction():
        connection.execute("SELECT pg_advisory_xact_lock(725198431)")
        connection.execute("CREATE SCHEMA IF NOT EXISTS tracker")
        connection.execute("REVOKE ALL ON SCHEMA tracker FROM PUBLIC")
        connection.execute("""
            CREATE TABLE IF NOT EXISTS tracker.schema_migrations (
                name TEXT PRIMARY KEY,
                checksum TEXT NOT NULL,
                applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )
        """)
        connection.execute("REVOKE ALL ON tracker.schema_migrations FROM PUBLIC")
        applied = connection.execute(
            "SELECT name, checksum FROM tracker.schema_migrations ORDER BY name"
        ).fetchall()
        _validate(applied, migrations, complete=False)
        for name, checksum, statement in migrations[len(applied):]:
            connection.execute(statement)
            connection.execute(
                "INSERT INTO tracker.schema_migrations (name, checksum) VALUES (%s, %s)",
                (name, checksum),
            )


def check_schema(connection: psycopg.Connection) -> None:
    """Runtime checks compatibility without making schema changes."""
    try:
        applied = connection.execute(
            "SELECT name, checksum FROM tracker.schema_migrations ORDER BY name"
        ).fetchall()
    except (psycopg.errors.UndefinedTable, psycopg.errors.InvalidSchemaName) as error:
        raise SchemaMismatch("PostgreSQL schema is missing; run migrations first") from error
    _validate(applied, _migrations(MIGRATIONS), complete=True)


if __name__ == "__main__":
    url = os.environ.get("TRACKER_MIGRATION_DATABASE_URL")
    if not url:
        raise SystemExit("Set TRACKER_MIGRATION_DATABASE_URL before running migrations")
    try:
        with psycopg.connect(url, sslmode="require", connect_timeout=10) as connection:
            migrate(connection)
    except (psycopg.Error, SchemaMismatch):
        # Connection exceptions can contain private host/user information.
        raise SystemExit("Migration failed; check credentials, connectivity, and migration history") from None
    print("PostgreSQL migrations applied successfully")
