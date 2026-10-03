from datetime import date
from tracker import record_review, get_latest_review, get_due_problems
from models import Problem, Review
from dataclasses import replace


def test_record_review_appends_attempt_without_replacing_history():
    previous_review = Review(
        problem_number = 1,
        reviewed_on = date(2026, 9, 8),
        mastery_level = "Learned Solution"
    )
    reviews = [replace(previous_review)]

    record_review(
        reviews,
        1,
        date(2026, 9, 9),
        "Solved Independently",
    )

    assert reviews == [
    previous_review,
    Review(
        problem_number=1,
        reviewed_on=date(2026, 9, 9),
        mastery_level="Solved Independently",
    ),
]

def test_get_newest_attempt_out_of_order():
    sample_review_one = Review(
            problem_number = 1,
            reviewed_on = date(2026, 9, 8),
            mastery_level = "Learned Solution"
    )

    sample_review_two = Review(
            problem_number = 1,
            reviewed_on = date(2026, 9, 9),
            mastery_level = "Learned Solution"
        )

    reviews = [sample_review_two, sample_review_one]
    latest_review = get_latest_review(reviews, 1)
    assert latest_review == sample_review_two
    
def test_get_correct_problem_despite_date():
    sample_review_one = Review(
            problem_number = 1,
            reviewed_on = date(2026, 9, 8),
            mastery_level = "Learned Solution"
    )

    sample_review_two = Review(
            problem_number = 2,
            reviewed_on = date(2026, 9, 9),
            mastery_level = "Learned Solution"
    )
    
    reviews = [sample_review_two, sample_review_one]
    latest_review = get_latest_review(reviews, 1)
    assert latest_review == sample_review_one
    
def test_no_match_return_none():
    sample_review_one = Review(
            problem_number = 1,
            reviewed_on = date(2026, 9, 8),
            mastery_level = "Learned Solution"
    )
    
    reviews = [sample_review_one]
    
    assert get_latest_review(reviews, 67) is None

def test_get_due_problems_includes_due_today_and_overdue():
    today = date(2026, 9, 20)
    reviews = [
    Review(
        problem_number = 1,
        reviewed_on = date(2026, 9, 5),
        mastery_level = "Solved Independently"
    ),
    Review(
        problem_number = 2,
        reviewed_on = date(2026, 9, 6),
        mastery_level = "Solved Independently"
    ),
    Review(
        problem_number = 3,
        reviewed_on = date(2026, 9, 7),
        mastery_level = "Solved Independently"
    )
    ]
    
    problems = [Problem(number = 1, name = "Two Sum", difficulty="Easy", topic="Arrays & Hashing", notes=""),
                Problem(number = 2, name = "Two Sum", difficulty="Easy", topic="Arrays & Hashing", notes=""),
                Problem(number = 3, name = "Two Sum", difficulty="Easy", topic="Arrays & Hashing", notes=""),
                Problem(number = 4, name = "Two Sum", difficulty="Easy", topic="Arrays & Hashing", notes="")]
    
    
    res = get_due_problems(problems, reviews, today)
    assert res == [problems[0], problems[1]]
    
def test_due_problems_excludes_archived_problems():
    today = date(2026, 9, 30)

    active = Problem(
        number=1,
        name="Two Sum",
        difficulty="Easy",
        topic="Arrays & Hashing",
        notes="",
    )
    archived = Problem(
        number=217,
        name="Contains Duplicate",
        difficulty="Easy",
        topic="Arrays & Hashing",
        notes="",
        archived=True,
    )
    reviews = [
        Review(1, date(2026, 9, 1), "Solved Independently"),
        Review(217, date(2026, 9, 1), "Solved Independently"),
    ]

    res = get_due_problems([active, archived], reviews, today)

    assert res == [active]
