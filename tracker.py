from datetime import date
from scheduler import calculate_next_review
from models import Problem, Review


def get_latest_review(reviews: list[Review], problem_number: int) -> Review | None:
    latest_review = None

    for review in reviews:
        if review.problem_number == problem_number:
            if (
                latest_review is None
                or review.reviewed_on > latest_review.reviewed_on
            ):
                latest_review = review

    return latest_review


def record_review(reviews: list[Review], problem_number: int, reviewed_on: date, mastery_level: str) -> None:
    review = Review(problem_number, reviewed_on, mastery_level)

    reviews.append(review)
    
def get_due_problems(problems: list[Problem], reviews: list[Review], today: date) -> list[Problem]:
    due = []
    
    for problem in problems:
        if problem.archived:
            continue
        latest_review = get_latest_review(reviews, problem.number)
        if latest_review is not None:
            next_review = calculate_next_review(latest_review.reviewed_on, latest_review.mastery_level)
            if next_review <= today:
                due.append(problem)
                
    return due