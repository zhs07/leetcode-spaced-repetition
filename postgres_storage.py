"""PostgreSQL operations scoped to one authenticated user's UUID.

The API must supply the verified identity, never a user ID from request JSON.
Each method uses one transaction. This module does not select an anonymous user,
run migrations, or touch the legacy SQLite database.
"""

from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from uuid import UUID

import psycopg
from psycopg.conninfo import conninfo_to_dict
from psycopg_pool import ConnectionPool, PoolTimeout

from importing import ImportedProblem, ImportSaveResult
from guest_limits import ensure_problem_capacity
from migrate import check_schema
from models import Problem, Review
from storage_errors import DuplicateProblem, ProblemNotFound, StorageError


def open_pool(database_url: str, *, sslmode: str = "verify-full") -> ConnectionPool:
    """Verify Supabase's certificate and hostname; local tests may disable TLS."""
    if not database_url.strip():
        raise ValueError("A PostgreSQL database URL is required")
    connection_options = {"sslmode": sslmode, "connect_timeout": 10}
    if sslmode == "verify-full":
        # Honor an explicitly supplied CA file; otherwise use Supabase's public
        # root certificate, bundled so Render needs no Mac-specific file path.
        connection_options["sslrootcert"] = conninfo_to_dict(database_url).get(
            "sslrootcert", str(Path(__file__).resolve().parent / "certificates" / "supabase-prod-ca-2021.crt"),
        )
    pool = ConnectionPool(
        database_url, min_size=1, max_size=4, timeout=10, max_waiting=16,
        kwargs=connection_options, open=False,
    )
    try:
        pool.open(wait=True, timeout=10)
        with pool.connection() as connection:
            check_schema(connection)
    except Exception:
        pool.close()
        raise
    return pool


@dataclass(frozen=True)
class PostgresStore:
    pool: ConnectionPool
    user_id: UUID
    problem_limit: int | None = None

    def __post_init__(self):
        if not isinstance(self.user_id, UUID) or self.user_id.int == 0:
            raise ValueError("A nonzero verified user UUID is required")
        if self.problem_limit is not None and (type(self.problem_limit) is not int or self.problem_limit < 1):
            raise ValueError("Problem limit must be a positive integer or None")

    @contextmanager
    def _connection(self):
        try:
            with self.pool.connection() as connection:
                yield connection
        except psycopg.errors.UniqueViolation as error:
            if error.diag.constraint_name == "problems_pkey":
                raise DuplicateProblem("Problem already exists") from error
            raise StorageError("Could not save data") from error
        except psycopg.errors.ForeignKeyViolation as error:
            raise ProblemNotFound("Problem not found") from error
        except (psycopg.Error, PoolTimeout) as error:
            raise StorageError("Database operation failed") from error

    def get_all_problems(self) -> list[Problem]:
        with self._connection() as connection:
            rows = connection.execute("""
                SELECT number, name, difficulty, topic, notes, archived,
                       review_due_on, historical_attempts
                FROM tracker.problems WHERE user_id = %s ORDER BY number
            """, (self.user_id,)).fetchall()
        return [Problem(*row) for row in rows]

    def get_all_reviews(self) -> list[Review]:
        with self._connection() as connection:
            rows = connection.execute("""
                SELECT problem_number, reviewed_on, mastery_level
                FROM tracker.reviews WHERE user_id = %s
                ORDER BY reviewed_on ASC, id DESC
            """, (self.user_id,)).fetchall()
        return [Review(*row) for row in rows]

    def _insert_review(self, connection, review: Review) -> None:
        connection.execute("""
            INSERT INTO tracker.reviews
                (user_id, problem_number, reviewed_on, mastery_level)
            VALUES (%s, %s, %s, %s)
        """, (self.user_id, review.problem_number, review.reviewed_on, review.mastery_level))

    def save_problem(self, problem: Problem) -> None:
        self.save_problem_with_first_attempt(problem)

    def _check_problem_capacity(self, connection, requested_numbers: list[int]) -> None:
        # Every addition uses the same per-owner transaction lock, including
        # permanent-account requests during an upgrade. Acquire it before any
        # row locks. Separate queries let a waiter see the previous commit at
        # PostgreSQL's default READ COMMITTED isolation level.
        connection.execute(
            "SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))",
            (f"tracker:problem-capacity:{self.user_id}",),
        )
        if self.problem_limit is None:
            return
        rows = connection.execute(
            "SELECT number FROM tracker.problems WHERE user_id = %s",
            (self.user_id,),
        ).fetchall()
        ensure_problem_capacity([row[0] for row in rows], requested_numbers, self.problem_limit)

    def save_problem_with_first_attempt(
        self, problem: Problem, first_attempt: Review | None = None,
    ) -> None:
        if first_attempt is not None and first_attempt.problem_number != problem.number:
            raise ValueError("First attempt must reference the same problem")
        with self._connection() as connection:
            self._check_problem_capacity(connection, [problem.number])
            connection.execute("""
                INSERT INTO tracker.problems
                    (user_id, number, name, difficulty, topic, notes, historical_attempts)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (self.user_id, problem.number, problem.name, problem.difficulty,
                  problem.topic, problem.notes, problem.historical_attempts))
            if first_attempt is not None:
                self._insert_review(connection, first_attempt)

    def save_review(self, review: Review) -> None:
        with self._connection() as connection:
            # Lock the parent first: serialize review/restore/archive operations
            # and avoid a shared-FK-lock -> update-lock upgrade deadlock.
            parent = connection.execute("""
                SELECT number FROM tracker.problems
                WHERE user_id = %s AND number = %s FOR UPDATE
            """, (self.user_id, review.problem_number)).fetchone()
            if parent is None:
                raise ProblemNotFound("Problem not found")
            self._insert_review(connection, review)
            connection.execute("""
                UPDATE tracker.problems SET review_due_on = NULL
                WHERE user_id = %s AND number = %s
            """, (self.user_id, review.problem_number))

    def save_imported_problems(self, imports: list[ImportedProblem]) -> ImportSaveResult:
        inserted = set()
        with self._connection() as connection:
            self._check_problem_capacity(connection, [item.problem.number for item in imports])
            # A consistent lock order avoids deadlocks for overlapping batches
            # submitted in different CSV orders. Preserve output order below.
            for imported in sorted(imports, key=lambda item: item.problem.number):
                source = imported.problem
                attempt = source.first_attempt
                row = connection.execute("""
                    INSERT INTO tracker.problems
                        (user_id, number, name, difficulty, topic, notes, historical_attempts)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (user_id, number) DO NOTHING RETURNING number
                """, (self.user_id, source.number, source.name, source.difficulty,
                      source.topic, source.notes, imported.total_attempts - 1)).fetchone()
                if row is not None:
                    if attempt is None:
                        raise ValueError(f"Problem #{source.number} has no latest attempt")
                    self._insert_review(connection, Review(
                        source.number, attempt.reviewed_on, attempt.mastery_level,
                    ))
                    inserted.add(source.number)

        imported_numbers, skipped_numbers = [], []
        for item in imports:
            number = item.problem.number
            if number in inserted:
                imported_numbers.append(number)
                inserted.remove(number)
            else:
                skipped_numbers.append(number)
        return ImportSaveResult(
            imported_numbers=imported_numbers, skipped_existing_numbers=skipped_numbers,
        )

    def delete_problem(self, problem_number: int) -> bool:
        with self._connection() as connection:
            return connection.execute("""
                DELETE FROM tracker.problems WHERE user_id = %s AND number = %s
            """, (self.user_id, problem_number)).rowcount == 1

    def archive_problem(self, problem_number: int) -> bool:
        with self._connection() as connection:
            return connection.execute("""
                UPDATE tracker.problems SET archived = TRUE
                WHERE user_id = %s AND number = %s
            """, (self.user_id, problem_number)).rowcount == 1

    def restore_problem(self, problem_number: int, restored_on: date) -> bool:
        with self._connection() as connection:
            return connection.execute("""
                UPDATE tracker.problems
                SET review_due_on = CASE WHEN archived THEN %s ELSE review_due_on END,
                    archived = FALSE
                WHERE user_id = %s AND number = %s
            """, (restored_on, self.user_id, problem_number)).rowcount == 1

    def get_problem_statement(self, problem_number: int) -> tuple[str, str | None] | None:
        with self._connection() as connection:
            return connection.execute("""
                SELECT html, title_slug FROM tracker.problem_statements
                WHERE user_id = %s AND problem_number = %s
            """, (self.user_id, problem_number)).fetchone()

    def save_problem_statement(
        self, problem_number: int, html: str, title_slug: str | None = None,
    ) -> None:
        with self._connection() as connection:
            connection.execute("""
                INSERT INTO tracker.problem_statements
                    (user_id, problem_number, html, title_slug)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (user_id, problem_number) DO UPDATE SET
                    html = excluded.html,
                    title_slug = COALESCE(excluded.title_slug, problem_statements.title_slug)
            """, (self.user_id, problem_number, html, title_slug))
