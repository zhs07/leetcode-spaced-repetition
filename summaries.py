from models import Problem, Review
from schemas import ProblemSummary
from tracker import get_latest_review, get_next_review_date
from scheduler import calculate_next_review


def build_problem_summary(problem: Problem, reviews: list[Review]) -> ProblemSummary:
    reviews_list = []

    for review in reviews:
        if review.problem_number == problem.number:
            reviews_list.append(review)

    most_recent_review = get_latest_review(reviews_list, problem.number)
    next_review = get_next_review_date(problem, reviews_list)

    if most_recent_review is not None:
        res = ProblemSummary(
            number=problem.number,
            name=problem.name,
            difficulty=problem.difficulty,
            topic=problem.topic,
            mastery_level=most_recent_review.mastery_level,
            next_review=next_review,
            attempts=len(reviews_list),
            notes=problem.notes,
            archived=problem.archived,
        )
    else:
        res = ProblemSummary(
            number=problem.number,
            name=problem.name,
            difficulty=problem.difficulty,
            topic=problem.topic,
            mastery_level=None,
            next_review=next_review,
            attempts=len(reviews_list),
            notes=problem.notes,
            archived=problem.archived,
        )

    return res