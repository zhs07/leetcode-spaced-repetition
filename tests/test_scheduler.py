from datetime import date

from scheduler import calculate_next_review

import pytest


@pytest.mark.parametrize("mastery, expected", [
    ("Learned Solution", date(2026, 9, 9)),
    ("Partial Recall", date(2026, 9, 11)),
    ("Solved with Struggle", date(2026, 9, 15)),
    ("Solved Independently", date(2026, 9, 22)),
    ("Mastered", date(2026, 10, 8)),
])
def test_mastery_schedules_review_from_attempt_date(mastery, expected):
    reviewed_on = date(2026, 9, 8)

    next_review = calculate_next_review(
        reviewed_on,
        mastery,
    )

    assert next_review == expected
    
def test_independent_review_crosses_month_boundary():
    reviewed_on = date(2026, 9, 29)
    
    next_review = calculate_next_review(
        reviewed_on,
        "Solved Independently"
    )
    
    assert next_review == date(2026, 10, 13)

def test_unknown_mastery_level_raises_error():
    with pytest.raises(ValueError):
        calculate_next_review(date(2026, 9, 8), "Unknown")
