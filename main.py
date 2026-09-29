from pathlib import Path

from fastapi import FastAPI, HTTPException

from models import Problem, Review
from storage import get_all_problems, get_all_reviews, save_review, save_problem, initialize_database
from datetime import date
from tracker import get_due_problems

from schemas import ReviewCreate, ProblemCreate, ProblemSummary
from contextlib import asynccontextmanager
from summaries import build_problem_summary

import sqlite3

DATABASE_PATH = str(Path(__file__).resolve().parent / "tracker.db")


@asynccontextmanager
async def lifespan(app: FastAPI):
    initialize_database(DATABASE_PATH)
    yield


app = FastAPI(lifespan=lifespan)


@app.get("/problems", response_model=list[Problem])
def list_problems() -> list[Problem]:
    return get_all_problems(DATABASE_PATH)


@app.get("/reviews", response_model=list[Review])
def list_reviews() -> list[Review]:
    return get_all_reviews(DATABASE_PATH)


@app.get("/problems/due", response_model=list[Problem])
def list_due_problems() -> list[Problem]:
    problems = list_problems()
    reviews = list_reviews()

    list_due_problems = get_due_problems(problems, reviews, date.today())
    return list_due_problems


@app.post("/reviews", response_model=Review, status_code=201)
def create_review(submission: ReviewCreate) -> Review:
    review = Review(problem_number=submission.problem_number,
                    reviewed_on=submission.reviewed_on,
                    mastery_level=submission.mastery_level)

    try:
        save_review(DATABASE_PATH, review)
    except sqlite3.IntegrityError as error:
        if "FOREIGN KEY constraint failed" in str(error):
            raise HTTPException(
                status_code=404,
                detail="Problem not found",
            ) from error
        raise

    return review

@app.post("/problems", response_model=Problem, status_code=201)
def create_problem(submission: ProblemCreate) -> Problem:
    problem = Problem(number=submission.number,
                      name=submission.name,
                      difficulty=submission.difficulty,
                      topic=submission.topic,
                      notes=submission.notes)
    
    try:
        save_problem(DATABASE_PATH, problem)
        
    except sqlite3.IntegrityError as error:
        if error.sqlite_errorcode == sqlite3.SQLITE_CONSTRAINT_PRIMARYKEY:
            raise HTTPException(
                status_code=409,
                detail="Problem already exists",
            ) from error
        raise
    
    return problem

@app.get("/problems/summary", response_model=list[ProblemSummary])
def list_problem_summaries() -> list[ProblemSummary]:
    problems = get_all_problems(DATABASE_PATH)
    reviews = get_all_reviews(DATABASE_PATH)
    list_of_problem_summary = []
    
    for problem in problems:
        problem_summary = build_problem_summary(problem, reviews)
        list_of_problem_summary.append(problem_summary)
        
    return list_of_problem_summary