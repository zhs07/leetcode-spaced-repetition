from models import Problem, Review
from schemas import ProblemSummary
from tracker import get_latest_review
from scheduler import calculate_next_review


def build_problem_summary(problem: Problem, reviews: list[Review]) -> ProblemSummary:
    reviews_list = []

    for review in reviews:
        if review.problem_number == problem.number:
            reviews_list.append(review)

    most_recent_review = get_latest_review(reviews_list, problem.number)

    if most_recent_review is not None:
        next_review = calculate_next_review(
            most_recent_review.reviewed_on, most_recent_review.mastery_level
        )
        if problem.archived == True:
            next_review = None
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
            next_review=None,
            attempts=len(reviews_list),
            notes=problem.notes,
            archived=problem.archived,
        )

    return res