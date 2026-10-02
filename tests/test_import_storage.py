"""Batch persistence, repeated imports, and atomic rollback checks."""

import sqlite3
from datetime import date

import pytest

from importing import ImportedProblem, ImportSaveResult
from models import Problem, Review
from schemas import AttemptCreate, ProblemCreate
from storage import (
    archive_problem,
    get_all_problems,
    get_all_reviews,
    initialize_database,
    save_imported_problems,
    save_problem,
    save_review,
)
from summaries import build_problem_summary


@pytest.fixture
def database_path(tmp_path):
    path = str(tmp_path / "batch-import.db")
    initialize_database(path)
    return path


def imported_item(number, total_attempts=4):
    return ImportedProblem(
        problem=ProblemCreate(
            number=number,
            name=f"Example {number}",
            difficulty="Easy",
            topic="Arrays",
            notes="Keep commas, and\nmultiple lines",
            first_attempt=AttemptCreate(
                reviewed_on=date(2026, 9, 10), mastery_level="Mastered",
            ),
        ),
        total_attempts=total_attempts,
    )


def test_batch_saves_metadata_counts_and_one_latest_review(database_path):
    items = [imported_item(1), imported_item(217, total_attempts=1)]

    result = save_imported_problems(database_path, items)

    assert result == ImportSaveResult(
        imported_numbers=[1, 217], skipped_existing_numbers=[],
    )
    problems = get_all_problems(database_path)
    assert problems == [
        Problem(
            item.problem.number, item.problem.name, item.problem.difficulty,
            item.problem.topic, item.problem.notes,
            historical_attempts=item.total_attempts - 1,
        )
        for item in items
    ]
    reviews = get_all_reviews(database_path)
    # Equal-date reviews are returned in descending insertion-ID order.
    assert reviews == [
        Review(217, date(2026, 9, 10), "Mastered"),
        Review(1, date(2026, 9, 10), "Mastered"),
    ]
    summaries = [build_problem_summary(problem, reviews) for problem in problems]
    assert [summary.attempts for summary in summaries] == [4, 1]
    assert all(summary.next_review == date(2026, 9, 24) for summary in summaries)


def test_batch_skips_existing_archived_problem_without_changing_history(database_path):
    original = Problem(1, "Original name", "Hard", "Graphs", "Original notes",
                       historical_attempts=7)
    save_problem(database_path, original)
    original_review = Review(1, date(2026, 9, 1), "Partial Recall")
    save_review(database_path, original_review)
    archive_problem(database_path, 1)
    before = get_all_problems(database_path)[0]

    result = save_imported_problems(database_path, [imported_item(1), imported_item(217)])

    assert result == ImportSaveResult(
        imported_numbers=[217], skipped_existing_numbers=[1],
    )
    assert get_all_problems(database_path)[0] == before
    reviews = get_all_reviews(database_path)
    assert [review for review in reviews if review.problem_number == 1] == [original_review]
    assert build_problem_summary(before, reviews).attempts == 8


def test_repeated_import_and_repeated_batch_numbers_do_not_inflate_counts(database_path):
    items = [imported_item(1), imported_item(1, total_attempts=99), imported_item(217)]
    assert save_imported_problems(database_path, items) == ImportSaveResult(
        imported_numbers=[1, 217], skipped_existing_numbers=[1],
    )
    before_problems = get_all_problems(database_path)
    before_reviews = get_all_reviews(database_path)

    assert save_imported_problems(database_path, items) == ImportSaveResult(
        imported_numbers=[], skipped_existing_numbers=[1, 1, 217],
    )
    assert get_all_problems(database_path) == before_problems
    assert get_all_reviews(database_path) == before_reviews


def test_empty_batch_returns_empty_result(database_path):
    assert save_imported_problems(database_path, []) == ImportSaveResult(
        imported_numbers=[], skipped_existing_numbers=[],
    )
    assert get_all_problems(database_path) == []
    assert get_all_reviews(database_path) == []


def test_missing_latest_attempt_rolls_back_earlier_items(database_path):
    missing_attempt = ImportedProblem(
        problem=ProblemCreate(number=217, name="Missing review", difficulty="Easy", topic="Arrays"),
        total_attempts=4,
    )

    with pytest.raises(ValueError):
        save_imported_problems(database_path, [imported_item(1), missing_attempt])

    assert get_all_problems(database_path) == []
    assert get_all_reviews(database_path) == []


def test_later_review_insert_failure_rolls_back_entire_batch(database_path):
    # Force a real SQL failure after the earlier item's two inserts and the
    # later item's problem INSERT. No personal database is involved.
    original = Problem(206, "Keep existing", "Easy", "Linked List", "Keep notes")
    save_problem(database_path, original)
    original_review = Review(206, date(2026, 9, 1), "Partial Recall")
    save_review(database_path, original_review)
    with sqlite3.connect(database_path) as connection:
        connection.executescript("""
            CREATE TRIGGER fail_later_import_review
            BEFORE INSERT ON reviews
            WHEN NEW.problem_number = 217
            BEGIN
                SELECT RAISE(ABORT, 'forced import failure');
            END;
        """)

    with pytest.raises(sqlite3.IntegrityError, match="forced import failure"):
        save_imported_problems(database_path, [imported_item(1), imported_item(217)])

    assert get_all_problems(database_path) == [original]
    assert get_all_reviews(database_path) == [original_review]
