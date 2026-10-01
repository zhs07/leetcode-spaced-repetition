from datetime import date
from scheduler import calculate_next_review
from models import Problem, Review


def get_latest_review(reviews: list[Review], problem_number: int) -> Review | None:
    latest_review = None

    for review in reviews:
        if review.problem_number == problem_number:
            if latest_review is None or review.reviewed_on > latest_review.reviewed_on:
                latest_review = review

    return latest_review


def record_review(
    reviews: list[Review], problem_number: int, reviewed_on: date, mastery_level: str
) -> None:
    review = Review(problem_number, reviewed_on, mastery_level)

    reviews.append(review)


def get_due_problems(
    problems: list[Problem], reviews: list[Review], today: date
) -> list[Problem]:
    due = []

    for problem in problems:
        next_review = get_next_review_date(problem, reviews)
        if next_review is not None and next_review <= today:
            due.append(problem)

    return due


def get_next_review_date(
    problem: Problem,
    reviews: list[Review],
) -> date | None:
    if problem.archived:
        return None

    if problem.review_due_on is not None:
        return problem.review_due_on

    latest_review = get_latest_review(reviews, problem.number)

    if latest_review is not None:
        return calculate_next_review(
            reviewed_on=latest_review.reviewed_on,
            mastery_level=latest_review.mastery_level,
        )
 
    return None
