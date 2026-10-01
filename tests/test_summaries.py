from datetime import date

from models import Problem, Review
from summaries import build_problem_summary


def test_archived_summary_pauses_schedule_and_preserves_history():
    problem = Problem(
        number=1,
        name="Two Sum",
        difficulty="Easy",
        topic="Arrays & Hashing",
        notes="Keep my approach",
        archived=True,
    )
    reviews = [
        Review(1, date(2026, 9, 1), "Mastered"),
    ]

    summary = build_problem_summary(problem, reviews)
    
    assert summary.archived is True
    assert summary.next_review is None
    assert summary.mastery_level == "Mastered"
    assert summary.attempts == 1
    assert summary.notes == problem.notes