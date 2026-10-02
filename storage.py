import sqlite3
from pathlib import Path
from models import Problem, Review
from datetime import date
from importing import ImportedProblem, ImportSaveResult


def get_connection(database_path: str) -> sqlite3.Connection:
    connection = sqlite3.connect(database_path)

    try:
        connection.execute("PRAGMA foreign_keys = ON")
    except:
        connection.close()
        raise

    return connection


def initialize_database(database_path: str) -> None:
    connection = get_connection(database_path)

    try:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS problems (
                number INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                difficulty TEXT NOT NULL,
                topic TEXT NOT NULL,
                notes TEXT NOT NULL,
                archived INTEGER NOT NULL DEFAULT 0 CHECK (archived IN (0, 1)),
                review_due_on TEXT,
                historical_attempts INTEGER NOT NULL DEFAULT 0 CHECK (historical_attempts >= 0)
            )
        """)
        connection.execute("""
            CREATE TABLE IF NOT EXISTS reviews (
                id INTEGER PRIMARY KEY,
                problem_number INTEGER NOT NULL,
                reviewed_on TEXT NOT NULL,
                mastery_level TEXT NOT NULL,
                FOREIGN KEY (problem_number) REFERENCES problems(number)
            )
        """)
        columns = connection.execute("PRAGMA table_info(problems)").fetchall()

        columns_names = {row[1] for row in columns}

        if "archived" not in columns_names:
            connection.execute("""
                ALTER TABLE problems
                ADD COLUMN archived INTEGER NOT NULL DEFAULT 0 CHECK (archived IN (0, 1))
                """)
        if "review_due_on" not in columns_names:
            connection.execute("""
                ALTER TABLE problems ADD COLUMN review_due_on TEXT
                """)
        if "historical_attempts" not in columns_names:
            connection.execute("""
                ALTER TABLE problems ADD COLUMN historical_attempts INTEGER NOT NULL DEFAULT 0 CHECK (historical_attempts >= 0)
                """)
        connection.commit()
        _repair_legacy_historical_counts(connection, database_path)
        connection.execute("""
            CREATE TABLE IF NOT EXISTS problem_statements (
                problem_number INTEGER PRIMARY KEY,
                html TEXT NOT NULL,
                title_slug TEXT,
                FOREIGN KEY (problem_number) REFERENCES problems(number) ON DELETE CASCADE
            )
        """)
        connection.commit()
    finally:
        connection.close()


def _repair_legacy_historical_counts(connection: sqlite3.Connection, database_path: str) -> None:
    """Upgrade the earlier nullable/TEXT count column without losing history."""
    column = next(row for row in connection.execute("PRAGMA table_info(problems)")
                  if row[1] == "historical_attempts")
    schema = connection.execute(
        "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'problems'"
    ).fetchone()[0]
    if (column[2].upper() == "INTEGER" and column[3] == 1
            and str(column[4]).strip("()") == "0"
            and "CHECK(HISTORICAL_ATTEMPTS>=0)" in "".join(schema.upper().split())):
        return

    # Keep a recoverable SQLite snapshot before rebuilding the legacy table.
    backup_path = Path(f"{database_path}.before-import-counts.bak")
    if not backup_path.exists():
        backup = sqlite3.connect(str(backup_path))
        try:
            connection.backup(backup)
        finally:
            backup.close()

    # Foreign keys must be disabled BEFORE the transaction to replace the
    # parent table. Reviews retain their IDs and still reference 'problems'.
    connection.execute("PRAGMA foreign_keys = OFF")
    try:
        connection.execute("BEGIN IMMEDIATE")
        rows = connection.execute("""
            SELECT number, name, difficulty, topic, notes, archived,
                   review_due_on, historical_attempts
            FROM problems
        """).fetchall()
        normalized_rows = []
        for row in rows:
            value = row[7]
            try:
                count = 0 if value is None else int(value)
                if (value is not None and not isinstance(value, (str, int))) or count < 0:
                    raise ValueError
            except (ValueError, TypeError, OverflowError) as error:
                raise ValueError(f"Invalid historical attempt count for problem #{row[0]}") from error
            normalized_rows.append((*row[:7], count))

        extra_schema = connection.execute("""
            SELECT sql FROM sqlite_master
            WHERE tbl_name = 'problems' AND type IN ('index', 'trigger') AND sql IS NOT NULL
        """).fetchall()
        connection.execute("""
            CREATE TABLE problems_count_migration (
                number INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                difficulty TEXT NOT NULL,
                topic TEXT NOT NULL,
                notes TEXT NOT NULL,
                archived INTEGER NOT NULL DEFAULT 0 CHECK (archived IN (0, 1)),
                review_due_on TEXT,
                historical_attempts INTEGER NOT NULL DEFAULT 0 CHECK (historical_attempts >= 0)
            )
        """)
        connection.executemany(
            "INSERT INTO problems_count_migration VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            normalized_rows,
        )
        connection.execute("DROP TABLE problems")
        connection.execute("ALTER TABLE problems_count_migration RENAME TO problems")
        for (statement,) in extra_schema:
            connection.execute(statement)
        if connection.execute("PRAGMA foreign_key_check").fetchall():
            raise sqlite3.IntegrityError("Historical count migration would break review references")
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.execute("PRAGMA foreign_keys = ON")


def save_problem(database_path: str, problem: Problem) -> None:
    connection = get_connection(database_path)

    try:
        connection.execute(
            """
            INSERT INTO problems (number, name, difficulty, topic, notes, historical_attempts)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                problem.number,
                problem.name,
                problem.difficulty,
                problem.topic,
                problem.notes,
                problem.historical_attempts,
            ),
        )
        connection.commit()
    finally:
        connection.close()


def get_all_problems(database_path: str) -> list[Problem]:
    connection = get_connection(database_path)

    try:
        rows = connection.execute("""
            SELECT number, name, difficulty, topic, notes, archived, review_due_on, historical_attempts
            FROM problems
            ORDER BY number
            """).fetchall()
    finally:
        connection.close()
    problems = []

    for row in rows:
        problem = Problem(
            number=row[0],
            name=row[1],
            difficulty=row[2],
            topic=row[3],
            notes=row[4],
            archived=bool(row[5]),
            review_due_on=(date.fromisoformat(row[6]) if row[6] is not None else None),
            historical_attempts=row[7],
        )
        problems.append(problem)

    return problems


def save_review(database_path: str, review: Review) -> None:
    connection = get_connection(database_path)

    try:
        connection.execute(
            """
            INSERT INTO reviews (problem_number, reviewed_on, mastery_level)
            VALUES (?, ?, ?)
            """,
            (
                review.problem_number,
                review.reviewed_on.isoformat(),
                review.mastery_level,
            ),
        )
        connection.execute(
            """
            UPDATE problems SET review_due_on = NULL WHERE number = ?
            """,
            (review.problem_number,),
        )
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def get_all_reviews(
    database_path: str,
) -> list[Review]:
    connection = get_connection(database_path)

    try:
        rows = connection.execute("""
            SELECT problem_number, reviewed_on, mastery_level
            FROM reviews
            ORDER BY reviewed_on ASC, id DESC
            """).fetchall()
    finally:
        connection.close()

    reviews = []

    for row in rows:
        review = Review(
            problem_number=row[0],
            reviewed_on=date.fromisoformat(row[1]),
            mastery_level=row[2],
        )
        reviews.append(review)

    return reviews


def save_problem_with_first_attempt(
    database_path: str,
    problem: Problem,
    first_attempt: Review | None = None,
) -> None:
    if first_attempt is not None and first_attempt.problem_number != problem.number:
        raise ValueError

    connection = get_connection(database_path)

    try:
        connection.execute(
            """
            INSERT INTO problems (number, name, difficulty, topic, notes, historical_attempts)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                problem.number,
                problem.name,
                problem.difficulty,
                problem.topic,
                problem.notes,
                problem.historical_attempts,
            ),
        )
        if first_attempt is not None:
            connection.execute(
                """
                    INSERT INTO reviews (problem_number, reviewed_on, mastery_level)
                    VALUES (?, ?, ?)
                    """,
                (
                    first_attempt.problem_number,
                    first_attempt.reviewed_on.isoformat(),
                    first_attempt.mastery_level,
                ),
            )
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def save_imported_problems(
    database_path: str,
    imports: list[ImportedProblem],
) -> ImportSaveResult:
    """Save accepted preview items together, preserving existing records.

    Store one latest review and total_attempts - 1 historical attempts for
    each new problem. Skip existing numbers, including repeats in this batch.
    A new imported problem must have a first_attempt; otherwise raise
    ValueError. Any failure rolls back every write from this batch.
    """
    connection = get_connection(database_path)
    imported_numbers: list[int] = []
    skipped_existing_numbers: list[int] = []

    try:
        # Reserve the SQLite writer before checking existing numbers, so
        # another writer cannot insert between our check and our INSERT.
        connection.execute("BEGIN IMMEDIATE")

        for imported in imports:
            source = imported.problem

            existing = connection.execute(
                "SELECT number FROM problems WHERE number = ?",
                (source.number,),
            ).fetchone()
            if existing is not None:
                skipped_existing_numbers.append(source.number)
                continue

            latest_attempt = source.first_attempt
            if latest_attempt is None:
                raise ValueError(f"Problem #{source.number} has no latest attempt")

            connection.execute(
                """
                INSERT INTO problems (number, name, difficulty, topic, notes, historical_attempts)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (source.number, source.name, source.difficulty, source.topic,
                 source.notes, imported.total_attempts - 1),
            )
            connection.execute(
                """
                INSERT INTO reviews (problem_number, reviewed_on, mastery_level)
                VALUES (?, ?, ?)
                """,
                (source.number, latest_attempt.reviewed_on.isoformat(), latest_attempt.mastery_level),
            )
            imported_numbers.append(source.number)

        connection.commit()
        return ImportSaveResult(
            imported_numbers=imported_numbers,
            skipped_existing_numbers=skipped_existing_numbers,
        )
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def delete_problem(database_path: str, problem_number: int) -> bool:
    connection = get_connection(database_path)

    try:
        connection.execute(
            "DELETE FROM reviews WHERE problem_number = ?",
            (problem_number,),
        )
        cursor = connection.execute(
            "DELETE FROM problems WHERE number = ?",
            (problem_number,),
        )

        connection.commit()

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()

    return cursor.rowcount == 1


def get_problem_statement(database_path: str, problem_number: int) -> tuple[str, str | None] | None:
    connection = get_connection(database_path)
    try:
        return connection.execute(
            "SELECT html, title_slug FROM problem_statements WHERE problem_number = ?",
            (problem_number,),
        ).fetchone()
    finally:
        connection.close()


def save_problem_statement(
    database_path: str, problem_number: int, html: str, title_slug: str | None = None,
) -> None:
    connection = get_connection(database_path)
    try:
        connection.execute("""
            INSERT INTO problem_statements (problem_number, html, title_slug)
            VALUES (?, ?, ?)
            ON CONFLICT(problem_number) DO UPDATE SET
                html = excluded.html,
                title_slug = COALESCE(excluded.title_slug, problem_statements.title_slug)
        """, (problem_number, html, title_slug))
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def archive_problem(database_path: str, problem_number: int) -> bool:
    connection = get_connection(database_path)

    try:
        cursor = connection.execute(
            "UPDATE problems SET archived = 1 WHERE number = ?",
            (problem_number,),
        )

        connection.commit()

        return cursor.rowcount == 1

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


def restore_problem(
    database_path: str,
    problem_number: int,
    restored_on: date,
) -> bool:
    connection = get_connection(database_path)

    try:
        connection.execute(
            """
            UPDATE problems
            SET archived = 0, review_due_on = ?
            WHERE number = ? and ARCHIVED = 1
            """,
            (restored_on.isoformat(), problem_number),
        )

        row = connection.execute(
            "SELECT number FROM problems WHERE number = ?",
            (problem_number,),
        ).fetchone()

        connection.commit()

        return row is not None

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()
