from models import Problem, Review
from datetime import date
from storage import (
    initialize_database,
    save_problem,
    get_all_problems,
    save_review,
    get_all_reviews,
    save_problem_with_first_attempt,
    delete_problem,
    archive_problem,
    restore_problem,
)
import sqlite3
import pytest
from dataclasses import replace
from tracker import get_due_problems
from summaries import build_problem_summary


def test_saved_problem_can_be_loaded(tmp_path):
    database_path = str(tmp_path / "test.db")
    initialize_database(database_path)

    problem = Problem(
        number=1,
        name="Two Sum",
        difficulty="Easy",
        topic="Arrays & Hashing",
        notes="Use a hashmap",
    )

    save_problem(database_path, problem)
    loaded = get_all_problems(database_path)

    assert loaded == [problem]


def test_saved_review_can_be_loaded(tmp_path):
    database_path = str(tmp_path / "test.db")
    initialize_database(database_path)

    problem = Problem(
        number=1,
        name="Two Sum",
        difficulty="Easy",
        topic="Arrays & Hashing",
        notes="",
    )
    save_problem(database_path, problem)

    review = Review(
        problem_number=1,
        reviewed_on=date(2026, 9, 20),
        mastery_level="Solved Independently",
    )

    save_review(database_path, review)
    loaded = get_all_reviews(database_path)

    assert loaded == [review]


def test_review_for_missing_problem_is_rejected(tmp_path):
    database_path = str(tmp_path / "test.db")
    initialize_database(database_path)

    review = Review(
        problem_number=999,
        reviewed_on=date(2026, 9, 20),
        mastery_level="Solved Independently",
    )

    with pytest.raises(sqlite3.IntegrityError, match="FOREIGN KEY"):
        save_review(database_path, review)


def test_problem_and_first_attempt_are_saved_together(tmp_path):
    database_path = str(tmp_path / "test.db")
    initialize_database(database_path)

    problem = Problem(
        number=1,
        name="Two Sum",
        difficulty="Easy",
        topic="Arrays & Hashing",
        notes="",
    )

    first_attempt = Review(
        problem_number=1,
        reviewed_on=date(2026, 9, 29),
        mastery_level="Partial Recall",
    )

    # Act: call your new function with all three arguments.
    save_problem_with_first_attempt(
        database_path, problem=problem, first_attempt=first_attempt
    )

    # Assert: load both collections and compare with expected lists.
    assert get_all_problems(database_path) == [problem]
    assert get_all_reviews(database_path) == [first_attempt]


def test_failed_first_attempt_rolls_back_problem(tmp_path):
    database_path = str(tmp_path / "test.db")
    initialize_database(database_path)

    # Test-only rule: make the review INSERT fail.
    connection = sqlite3.connect(database_path)
    try:
        connection.execute("""
            CREATE TRIGGER reject_review
            BEFORE INSERT ON reviews
            BEGIN
                SELECT RAISE(ABORT, 'forced review failure');
            END;
        """)
        connection.commit()
    finally:
        connection.close()

    problem = Problem(
        number=1,
        name="Two Sum",
        difficulty="Easy",
        topic="Arrays & Hashing",
        notes="",
    )

    first_attempt = Review(
        problem_number=1,
        reviewed_on=date(2026, 9, 29),
        mastery_level="Partial Recall",
    )

    with pytest.raises(sqlite3.IntegrityError, match="forced review failure"):
        save_problem_with_first_attempt(database_path, problem, first_attempt)

    assert get_all_reviews(database_path) == []
    assert get_all_problems(database_path) == []


def test_delete_problem_removes_only_its_data(tmp_path):
    database_path = str(tmp_path / "test.db")
    initialize_database(database_path)

    target = Problem(
        number=1,
        name="Two Sum",
        difficulty="Easy",
        topic="Arrays & Hashing",
        notes="",
    )
    other = Problem(
        number=217,
        name="Contains Duplicate",
        difficulty="Easy",
        topic="Arrays & Hashing",
        notes="",
    )

    target_review = Review(
        problem_number=1,
        reviewed_on=date(2026, 9, 29),
        mastery_level="Partial Recall",
    )
    other_review = Review(
        problem_number=217,
        reviewed_on=date(2026, 9, 29),
        mastery_level="Solved Independently",
    )

    save_problem(database_path, target)
    save_problem(database_path, other)

    save_review(database_path, target_review)
    save_review(database_path, other_review)

    deleted = delete_problem(database_path, 1)

    # Assert: check the result and what remains in the database.
    assert deleted is True
    assert get_all_problems(database_path) == [other]
    assert get_all_reviews(database_path) == [other_review]


def test_delete_problem_without_reviews(tmp_path):
    database_path = str(tmp_path / "test.db")
    initialize_database(database_path)

    problem = Problem(
        number=1,
        name="Two Sum",
        difficulty="Easy",
        topic="Arrays & Hashing",
        notes="",
    )
    save_problem(database_path, problem)

    deleted = delete_problem(database_path, problem.number)

    assert deleted is True
    assert get_all_problems(database_path) == []
    assert get_all_reviews(database_path) == []


def test_delete_missing_problem_returns_false(tmp_path):
    database_path = str(tmp_path / "test.db")
    initialize_database(database_path)

    deleted = delete_problem(database_path, 999)

    assert deleted is False
    assert get_all_problems(database_path) == []
    assert get_all_reviews(database_path) == []


def test_failed_problem_delete_restores_reviews(tmp_path):
    database_path = str(tmp_path / "test.db")
    initialize_database(database_path)

    problem = Problem(
        number=1,
        name="Two Sum",
        difficulty="Easy",
        topic="Arrays & Hashing",
        notes="",
    )
    review = Review(
        problem_number=1,
        reviewed_on=date(2026, 9, 29),
        mastery_level="Partial Recall",
    )

    save_problem(database_path, problem)
    save_review(database_path, review)

    # Test-only rule: force the second DELETE to fail.
    connection = sqlite3.connect(database_path)
    try:
        connection.execute("""
            CREATE TRIGGER reject_problem_delete
            BEFORE DELETE ON problems
            BEGIN
                SELECT RAISE(ABORT, 'forced problem deletion failure');
            END;
        """)
        connection.commit()
    finally:
        connection.close()

    with pytest.raises(
        sqlite3.IntegrityError,
        match="forced problem deletion failure",
    ):
        delete_problem(database_path, problem.number)

    assert get_all_problems(database_path) == [problem]
    assert get_all_reviews(database_path) == [review]


def test_archive_migration_preserves_existing_data(tmp_path):
    database_path = str(tmp_path / "test.db")

    # Recreate the OLD schema: no archived column.
    connection = sqlite3.connect(database_path)
    try:
        connection.executescript("""
            CREATE TABLE problems (
                number INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                difficulty TEXT NOT NULL,
                topic TEXT NOT NULL,
                notes TEXT NOT NULL
            );
            CREATE TABLE reviews (
                id INTEGER PRIMARY KEY,
                problem_number INTEGER NOT NULL,
                reviewed_on TEXT NOT NULL,
                mastery_level TEXT NOT NULL,
                FOREIGN KEY (problem_number) REFERENCES problems(number)
            );
        """)
        connection.commit()
    finally:
        connection.close()

    problem = Problem(
        number=1,
        name="Two Sum",
        difficulty="Easy",
        topic="Arrays & Hashing",
        notes="Keep my notes",
    )
    review = Review(
        problem_number=1,
        reviewed_on=date(2026, 9, 29),
        mastery_level="Partial Recall",
    )

    save_problem(database_path, problem)
    connection = sqlite3.connect(database_path)

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
        connection.commit()
    finally:
        connection.close()

    initialize_database(database_path)
    initialize_database(database_path)

    loaded_problem = get_all_problems(database_path)
    assert loaded_problem == [problem]
    assert loaded_problem[0].archived is False

    assert get_all_reviews(database_path) == [review]


def test_archive_preserves_problem_and_history(tmp_path):
    database_path = str(tmp_path / "test.db")
    initialize_database(database_path)

    target = Problem(
        number=1,
        name="Two Sum",
        difficulty="Easy",
        topic="Arrays & Hashing",
        notes="Keep these notes",
    )
    other = Problem(
        number=217,
        name="Contains Duplicate",
        difficulty="Easy",
        topic="Arrays & Hashing",
        notes="",
    )
    review = Review(
        problem_number=1,
        reviewed_on=date(2026, 9, 29),
        mastery_level="Partial Recall",
    )

    save_problem(database_path, target)
    save_problem(database_path, other)
    save_review(database_path, review)

    res = archive_problem(database_path, target.number)

    assert res is True
    assert get_all_problems(database_path) == [replace(target, archived=True), other]
    assert get_all_reviews(database_path) == [review]

    res_two = archive_problem(database_path, target.number)
    assert res_two is True
    assert get_all_problems(database_path) == [replace(target, archived=True), other]
    assert get_all_reviews(database_path) == [review]


def test_archive_missing_problem_returns_false(tmp_path):
    database_path = str(tmp_path / "test.db")
    initialize_database(database_path)

    res = archive_problem(database_path, 999)
    assert res is False
    assert get_all_problems(database_path) == []
    assert get_all_reviews(database_path) == []
    
    
def test_restored_problem_is_due_until_an_attempt_is_saved(tmp_path):
    database_path = str(tmp_path / "test.db")
    initialize_database(database_path)
    today = date(2026, 9, 30)

    problem = Problem(
        number=1,
        name="Two Sum",
        difficulty="Easy",
        topic="Arrays & Hashing",
        notes="Keep my approach",
    )
    old_review = Review(
        problem_number=1,
        reviewed_on=date(2026, 9, 29),
        mastery_level="Mastered",
    )
    save_problem(database_path, problem)
    save_review(database_path, old_review)
    
    
    archive_problem(database_path, problem.number)
    res = restore_problem(database_path, problem.number, today)
    assert res is True

    problems = get_all_problems(database_path)
    reviews = get_all_reviews(database_path)

    assert problems == [replace(problem, review_due_on=today)]
    assert reviews == [old_review]
    assert get_due_problems(problems, reviews, today) == problems
    assert build_problem_summary(problems[0], reviews).next_review == today

    new_review = Review(
        problem_number=1,
        reviewed_on=today,
        mastery_level="Solved Independently",
    )

    save_review(database_path, new_review)

    # Reload: these earlier Python lists don't update automatically.
    problems = get_all_problems(database_path)
    reviews = get_all_reviews(database_path)
    summary = build_problem_summary(problems[0], reviews)
    
    assert problems[0].review_due_on is None
    assert reviews == [old_review, new_review]
    assert summary.next_review == date(2026, 10, 7)
    assert summary.attempts == 2
    assert get_due_problems(problems, reviews, today) == []
    
def test_failed_override_reset_rolls_back_new_attempt(tmp_path):
    database_path = str(tmp_path / "test.db")
    initialize_database(database_path)
    today = date(2026, 9, 30)

    problem = Problem(
        number=1,
        name="Two Sum",
        difficulty="Easy",
        topic="Arrays & Hashing",
        notes="Keep my approach",
    )
    old_review = Review(
        problem_number=1,
        reviewed_on=date(2026, 9, 29),
        mastery_level="Mastered",
    )

    save_problem(database_path, problem)
    save_review(database_path, old_review)
    archive_problem(database_path, problem.number)
    restore_problem(database_path, problem.number, today)

    # Install this AFTER restoring, so setup can succeed.
    connection = sqlite3.connect(database_path)
    try:
        connection.execute("""
            CREATE TRIGGER reject_override_reset
            BEFORE UPDATE OF review_due_on ON problems
            BEGIN
                SELECT RAISE(ABORT, 'forced override reset failure');
            END;
        """)
        connection.commit()
    finally:
        connection.close()

    new_review = Review(
        problem_number=1,
        reviewed_on=today,
        mastery_level="Solved Independently",
    )

    with pytest.raises(
        sqlite3.IntegrityError,
        match="forced override reset failure",
    ):
        save_review(database_path, new_review)

    assert get_all_reviews(database_path) == [old_review]

    problems = get_all_problems(database_path)

    assert problems == [replace(problem, review_due_on=today)]
    
    assert get_due_problems(problems, [old_review], today) == problems
