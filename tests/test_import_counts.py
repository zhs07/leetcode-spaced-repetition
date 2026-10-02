"""Historical-count checks for the import storage foundation."""

import sqlite3
from datetime import date
from pathlib import Path

import pytest

from models import Problem, Review
from storage import (
    archive_problem,
    get_all_problems,
    get_all_reviews,
    initialize_database,
    save_problem,
    save_problem_with_first_attempt,
    save_review,
)
from summaries import build_problem_summary


def test_historical_count_migration_preserves_existing_records(tmp_path):
    database_path = str(tmp_path / "old.db")
    with sqlite3.connect(database_path) as connection:
        connection.executescript("""
            CREATE TABLE problems (
                number INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                difficulty TEXT NOT NULL,
                topic TEXT NOT NULL,
                notes TEXT NOT NULL,
                archived INTEGER NOT NULL DEFAULT 0,
                review_due_on TEXT
            );
            CREATE TABLE reviews (
                id INTEGER PRIMARY KEY,
                problem_number INTEGER NOT NULL,
                reviewed_on TEXT NOT NULL,
                mastery_level TEXT NOT NULL,
                FOREIGN KEY (problem_number) REFERENCES problems(number)
            );
        """)
        connection.execute(
            "INSERT INTO problems VALUES (?, ?, ?, ?, ?, ?, ?)",
            (1, "Two Sum", "Easy", "Arrays", "Keep notes", 1, "2026-10-01"),
        )
        connection.execute(
            "INSERT INTO reviews VALUES (?, ?, ?, ?)",
            (1, 1, "2026-09-10", "Mastered"),
        )

    initialize_database(database_path)
    initialize_database(database_path)

    assert get_all_problems(database_path) == [
        Problem(
            1, "Two Sum", "Easy", "Arrays", "Keep notes",
            archived=True, review_due_on=date(2026, 10, 1), historical_attempts=0,
        )
    ]
    assert get_all_reviews(database_path) == [Review(1, date(2026, 9, 10), "Mastered")]


def test_imported_count_persists_and_new_attempt_increments_total(tmp_path):
    database_path = str(tmp_path / "import.db")
    initialize_database(database_path)
    problem = Problem(
        1, "Two Sum", "Easy", "Arrays", "Keep notes", historical_attempts=3
    )
    latest_attempt = Review(1, date(2026, 9, 10), "Mastered")
    save_problem_with_first_attempt(database_path, problem, latest_attempt)

    loaded = get_all_problems(database_path)[0]
    reviews = get_all_reviews(database_path)
    assert loaded == problem
    assert reviews == [latest_attempt]
    summary = build_problem_summary(loaded, reviews)
    assert summary.attempts == 4
    assert summary.next_review == date(2026, 9, 24)

    new_attempt = Review(1, date(2026, 10, 1), "Solved Independently")
    save_review(database_path, new_attempt)
    loaded = get_all_problems(database_path)[0]
    reviews = get_all_reviews(database_path)
    assert loaded.historical_attempts == 3
    assert reviews == [latest_attempt, new_attempt]
    summary = build_problem_summary(loaded, reviews)
    assert summary.attempts == 5
    assert summary.next_review == date(2026, 10, 8)

    archive_problem(database_path, 1)
    summary = build_problem_summary(get_all_problems(database_path)[0], reviews)
    assert summary.attempts == 5
    assert summary.next_review is None


def test_historical_count_without_review_has_no_invented_schedule(tmp_path):
    database_path = str(tmp_path / "count-only.db")
    initialize_database(database_path)
    problem = Problem(1, "Two Sum", "Easy", "Arrays", "", historical_attempts=3)
    save_problem(database_path, problem)

    loaded = get_all_problems(database_path)[0]
    assert loaded == problem
    summary = build_problem_summary(loaded, get_all_reviews(database_path))
    assert summary.attempts == 3
    assert summary.mastery_level is None
    assert summary.next_review is None

    with pytest.raises(sqlite3.IntegrityError):
        save_problem(
            database_path,
            Problem(2, "Invalid count", "Easy", "Arrays", "", historical_attempts=-1),
        )
    assert get_all_problems(database_path) == [problem]


def legacy_count_database(database_path, column_type="TEXT", count="3"):
    with sqlite3.connect(database_path) as connection:
        connection.executescript(f"""
            CREATE TABLE problems (
                number INTEGER PRIMARY KEY,
                name TEXT NOT NULL, difficulty TEXT NOT NULL,
                topic TEXT NOT NULL, notes TEXT NOT NULL,
                archived INTEGER NOT NULL DEFAULT 0,
                review_due_on TEXT,
                historical_attempts {column_type}
            );
            CREATE TABLE reviews (
                id INTEGER PRIMARY KEY, problem_number INTEGER NOT NULL,
                reviewed_on TEXT NOT NULL, mastery_level TEXT NOT NULL,
                FOREIGN KEY (problem_number) REFERENCES problems(number)
            );
            CREATE INDEX problems_topic_index ON problems(topic);
        """)
        connection.executemany("INSERT INTO problems VALUES (?, ?, ?, ?, ?, ?, ?, ?)", [
            (1, "Existing problem", "Easy", "Arrays", "Original notes", 1, "2026-10-01", None),
            (2, "Imported problem", "Medium", "Graphs", "Imported notes", 0, None, count),
        ])
        connection.execute("INSERT INTO reviews VALUES (?, ?, ?, ?)",
                           (42, 2, "2026-09-10", "Mastered"))


@pytest.mark.parametrize("column_type", ["TEXT", "INTEGER"])
def test_legacy_nullable_counts_are_repaired_with_backup_and_preserved_history(tmp_path, column_type):
    database_path = str(tmp_path / "legacy.db")
    legacy_count_database(database_path, column_type)

    initialize_database(database_path)
    backup_path = Path(f"{database_path}.before-import-counts.bak")
    assert backup_path.exists()
    snapshot = backup_path.read_bytes()
    initialize_database(database_path)
    assert backup_path.read_bytes() == snapshot

    problems = get_all_problems(database_path)
    assert problems == [
        Problem(1, "Existing problem", "Easy", "Arrays", "Original notes",
                archived=True, review_due_on=date(2026, 10, 1), historical_attempts=0),
        Problem(2, "Imported problem", "Medium", "Graphs", "Imported notes", historical_attempts=3),
    ]
    reviews = get_all_reviews(database_path)
    assert reviews == [Review(2, date(2026, 9, 10), "Mastered")]
    assert build_problem_summary(problems[1], reviews).attempts == 4
    with sqlite3.connect(database_path) as connection:
        column = {row[1]: row for row in connection.execute("PRAGMA table_info(problems)")}["historical_attempts"]
        assert column[2:5] == ("INTEGER", 1, "0")
        assert connection.execute("SELECT id FROM reviews").fetchall() == [(42,)]
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
        assert connection.execute("SELECT name FROM sqlite_master WHERE name = 'problems_topic_index'").fetchone()
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute("UPDATE problems SET historical_attempts = -1 WHERE number = 2")
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute("UPDATE problems SET historical_attempts = NULL WHERE number = 2")
    with sqlite3.connect(str(backup_path)) as connection:
        assert connection.execute("SELECT historical_attempts FROM problems WHERE number = 1").fetchone() == (None,)


@pytest.mark.parametrize("invalid_count", ["bad", "-1", "1.5"])
def test_legacy_count_repair_rejects_invalid_values_without_losing_data(tmp_path, invalid_count):
    database_path = str(tmp_path / "invalid-legacy.db")
    legacy_count_database(database_path, count=invalid_count)

    with pytest.raises(ValueError, match="Invalid historical attempt count"):
        initialize_database(database_path)

    with sqlite3.connect(database_path) as connection:
        assert connection.execute("SELECT historical_attempts FROM problems ORDER BY number").fetchall() == [(None,), (invalid_count,)]
        assert connection.execute("SELECT id FROM reviews").fetchall() == [(42,)]
        assert connection.execute("SELECT name FROM sqlite_master WHERE name = 'problems_count_migration'").fetchone() is None


def test_legacy_count_repair_rolls_back_if_table_replacement_fails(tmp_path, monkeypatch):
    import storage
    database_path = str(tmp_path / "rollback-legacy.db")
    legacy_count_database(database_path)

    class FailingConnection(sqlite3.Connection):
        def execute(self, sql, *args):
            if sql.startswith("ALTER TABLE problems_count_migration"):
                raise sqlite3.OperationalError("forced replacement failure")
            return super().execute(sql, *args)

    def failing_connection(path):
        connection = sqlite3.connect(path, factory=FailingConnection)
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    monkeypatch.setattr(storage, "get_connection", failing_connection)
    with pytest.raises(sqlite3.OperationalError, match="forced replacement failure"):
        initialize_database(database_path)

    with sqlite3.connect(database_path) as connection:
        assert connection.execute("SELECT number, historical_attempts FROM problems ORDER BY number").fetchall() == [(1, None), (2, "3")]
        assert connection.execute("SELECT id FROM reviews").fetchall() == [(42,)]
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
        assert connection.execute("SELECT name FROM sqlite_master WHERE name = 'problems_count_migration'").fetchone() is None
