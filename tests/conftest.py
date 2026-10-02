"""Shared disposable PostgreSQL fixtures; never use a configured application DB."""
import os
from pathlib import Path
import shutil
import subprocess
from tempfile import TemporaryDirectory
from uuid import uuid4

import psycopg
from psycopg import sql
from psycopg.conninfo import make_conninfo
import pytest
from migrate import migrate

@pytest.fixture(scope="session")
def postgres_cluster():
    bindir = os.environ.get("PG_BIN")
    if not bindir:
        executable = shutil.which("initdb")
        bindir = str(Path(executable).parent) if executable else "/opt/homebrew/opt/postgresql@17/bin"
    initdb, pg_ctl = Path(bindir) / "initdb", Path(bindir) / "pg_ctl"
    if not initdb.is_file() or not pg_ctl.is_file():
        pytest.skip("PostgreSQL binaries required: set PG_BIN to run integration tests")

    # Short path avoids Unix socket path-length limits on macOS. Private directory
    # and disabled TCP mean the test-only trust authentication is not public.
    with TemporaryDirectory(prefix="tracker-pg-", dir="/private/tmp" if Path("/private/tmp").exists() else None) as folder:
        root = Path(folder)
        data = root / "data"
        subprocess.run([
            str(initdb), "-D", str(data), "--username=tracker_test_admin",
            "--auth-local=trust", "--auth-host=reject", "--encoding=UTF8", "--no-locale",
        ], check=True, capture_output=True, text=True)
        with (data / "postgresql.conf").open("a") as config:
            config.write(f"\nlisten_addresses = ''\nunix_socket_directories = '{root}'\n"
                         "max_connections = 20\nfsync = off\n")
        try:
            subprocess.run([
                str(pg_ctl), "-D", str(data), "-l", str(root / "server.log"), "-w", "start",
            ], check=True, capture_output=True, text=True)
            dsn = make_conninfo(host=str(root), dbname="postgres", user="tracker_test_admin")
            with psycopg.connect(dsn, autocommit=True) as connection:
                connection.execute("CREATE ROLE tracker_test_runtime LOGIN")
                connection.execute("CREATE ROLE tracker_test_stranger LOGIN")
            yield dsn
        finally:
            if (data / "postmaster.pid").exists():
                subprocess.run([
                    str(pg_ctl), "-D", str(data), "-m", "immediate", "-w", "stop",
                ], check=True, capture_output=True, text=True)


@pytest.fixture
def database(postgres_cluster):
    name = "tracker_test_" + uuid4().hex
    with psycopg.connect(postgres_cluster, autocommit=True) as connection:
        connection.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
    dsn = make_conninfo(postgres_cluster, dbname=name)
    try:
        with psycopg.connect(dsn) as connection:
            migrate(connection)
            connection.execute("GRANT USAGE ON SCHEMA tracker TO tracker_test_runtime")
            connection.execute("GRANT SELECT ON tracker.schema_migrations TO tracker_test_runtime")
            connection.execute("""
                GRANT SELECT, INSERT, UPDATE, DELETE ON
                tracker.problems, tracker.reviews, tracker.problem_statements
                TO tracker_test_runtime
            """)
            connection.execute("GRANT USAGE ON ALL SEQUENCES IN SCHEMA tracker TO tracker_test_runtime")
        yield dsn
    finally:
        with psycopg.connect(postgres_cluster, autocommit=True) as connection:
            connection.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(name)))
