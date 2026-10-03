from pathlib import Path
from random import choice

from typing import Annotated
from fastapi import APIRouter, Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from starlette.middleware.body_limit import RequestBodyLimitMiddleware
from auth import TokenVerifier
from settings import Settings
from postgres_storage import PostgresStore, open_pool
from sqlite_store import SQLiteStore
from storage_errors import DuplicateProblem, ProblemNotFound, StorageError
from guest_limits import DEFAULT_GUEST_PROBLEM_LIMIT, ProblemLimitExceeded
from input_limits import MAX_REQUEST_BYTES

from models import Problem, Review
from storage import initialize_database
from datetime import date
from tracker import get_due_problems

from schemas import (
    ReviewCreate, ProblemCreate, ProblemSummary, ImportPreviewRequest,
    PracticePick, StatementSaveRequest,
)
from importing import ImportPreview, ImportResult, preview_notion_csv
from contextlib import asynccontextmanager
from summaries import build_problem_summary
from statements import fetch_statement, parse_statement, pasted_statement_html, statement_url, StatementUnavailable


DATABASE_PATH = str(Path(__file__).resolve().parent / "tracker.db")


security = HTTPBearer(auto_error=False)
router = APIRouter()


def get_store(request: Request, credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(security)]):
    if request.app.state.settings.mode == "local":
        return SQLiteStore(DATABASE_PATH)
    if credentials is None:
        raise HTTPException(401, "Please sign in to continue.", headers={"WWW-Authenticate": "Bearer"})
    user = request.app.state.verifier.verify(credentials.credentials)
    return PostgresStore(
        request.app.state.pool, user.user_id,
        problem_limit=DEFAULT_GUEST_PROBLEM_LIMIT if user.is_anonymous else None,
    )


Store = Annotated[PostgresStore | SQLiteStore, Depends(get_store)]


def _practice_statement(problem_number: int, store: PostgresStore | SQLiteStore) -> PracticePick:
    if not any(problem.number == problem_number for problem in store.get_all_problems()):
        raise HTTPException(status_code=404, detail="Problem no longer exists in your list")
    cached = store.get_problem_statement(problem_number)
    if cached is not None:
        html, slug = cached
        return PracticePick(problem_number=problem_number, statement=parse_statement(html), leetcode_url=statement_url(slug))
    try:
        html, slug = fetch_statement(problem_number)
    except StatementUnavailable as error:
        return PracticePick(
            problem_number=problem_number, statement=None,
            statement_error=str(error), leetcode_url=statement_url(error.slug),
        )
    try:
        store.save_problem_statement(problem_number, html, slug)
    except ProblemNotFound as error:
        raise HTTPException(status_code=404, detail="Problem no longer exists in your list") from error
    return PracticePick(problem_number=problem_number, statement=parse_statement(html), leetcode_url=statement_url(slug))


@router.post("/practice/random", response_model=PracticePick)
def pick_random_due_problem(store: Store) -> PracticePick:
    due = get_due_problems(store.get_all_problems(), store.get_all_reviews(), date.today())
    if not due:
        raise HTTPException(status_code=404, detail="You're caught up. There are no due or overdue problems.")
    return _practice_statement(choice(due).number, store)


@router.post("/practice/{problem_number}/statement/load", response_model=PracticePick)
def load_practice_statement(problem_number: int, store: Store) -> PracticePick:
    """Retry the same selected problem, without drawing a different one."""
    return _practice_statement(problem_number, store)


@router.put("/practice/{problem_number}/statement", response_model=PracticePick)
def save_pasted_statement(problem_number: int, submission: StatementSaveRequest, store: Store) -> PracticePick:
    html = pasted_statement_html(submission.text)
    try:
        store.save_problem_statement(problem_number, html)
    except ProblemNotFound as error:
        raise HTTPException(status_code=404, detail="Problem no longer exists in your list") from error
    cached = store.get_problem_statement(problem_number)
    return PracticePick(problem_number=problem_number, statement=parse_statement(html), leetcode_url=statement_url(cached[1] if cached else None))


@router.post("/imports/notion/preview", response_model=ImportPreview)
def preview_notion_import(submission: ImportPreviewRequest, store: Store) -> ImportPreview:
    """Preview CSV text without saving imported problems or attempts."""
    try:
        return preview_notion_csv(submission.csv_text)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.post("/imports/notion", response_model=ImportResult)
def import_notion_csv(submission: ImportPreviewRequest, store: Store) -> ImportResult:
    """Revalidate the original CSV and save its valid rows in one transaction."""
    try:
        preview = preview_notion_csv(submission.csv_text)
        saved = store.save_imported_problems(preview.problems)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except ProblemLimitExceeded as error:
        raise HTTPException(status_code=403, detail=str(error)) from error
    except StorageError as error:
        raise HTTPException(
            status_code=500,
            detail="Import failed. No problems were saved. Please try again.",
        ) from error

    return ImportResult(
        imported_numbers=saved.imported_numbers,
        skipped_existing_numbers=saved.skipped_existing_numbers,
        errors=preview.errors,
        skipped_rows=preview.skipped_rows,
    )


@router.get("/problems", response_model=list[Problem])
def list_problems(store: Store) -> list[Problem]:
    return store.get_all_problems()


@router.get("/reviews", response_model=list[Review])
def list_reviews(store: Store) -> list[Review]:
    return store.get_all_reviews()


@router.get("/problems/due", response_model=list[Problem])
def list_due_problems(store: Store) -> list[Problem]:
    problems = store.get_all_problems()
    reviews = store.get_all_reviews()

    list_due_problems = get_due_problems(problems, reviews, date.today())
    return list_due_problems


@router.post("/reviews", response_model=Review, status_code=201)
def create_review(submission: ReviewCreate, store: Store) -> Review:
    review = Review(
        problem_number=submission.problem_number,
        reviewed_on=submission.reviewed_on,
        mastery_level=submission.mastery_level,
    )

    try:
        store.save_review(review)
    except ProblemNotFound as error:
        raise HTTPException(404, "Problem not found") from error

    return review


@router.post("/problems", response_model=Problem, status_code=201)
def create_problem(submission: ProblemCreate, store: Store) -> Problem:
    problem = Problem(
        number=submission.number,
        name=submission.name,
        difficulty=submission.difficulty,
        topic=submission.topic,
        notes=submission.notes,
    )

    first_attempt = None

    if submission.first_attempt is not None:
        first_attempt = Review(
            problem_number=problem.number,
            reviewed_on=submission.first_attempt.reviewed_on,
            mastery_level=submission.first_attempt.mastery_level,
        )

    try:
        store.save_problem_with_first_attempt(problem, first_attempt)

    except DuplicateProblem as error:
        raise HTTPException(409, "Problem already exists") from error

    return problem


@router.get("/problems/summary", response_model=list[ProblemSummary])
def list_problem_summaries(store: Store) -> list[ProblemSummary]:
    problems = store.get_all_problems()
    reviews = store.get_all_reviews()
    list_of_problem_summary = []

    for problem in problems:
        problem_summary = build_problem_summary(problem, reviews)
        list_of_problem_summary.append(problem_summary)

    return list_of_problem_summary


@router.get("/problems/{problem_number}/summary", response_model=ProblemSummary)
def get_problem_summary(problem_number: int, store: Store) -> ProblemSummary:
    problem = next((problem for problem in store.get_all_problems() if problem.number == problem_number), None)
    if problem is None:
        raise HTTPException(status_code=404, detail="Problem no longer exists in your list")
    return build_problem_summary(problem, store.get_all_reviews())


@router.delete("/problems/{problem_number}")
def remove_problem(problem_number: int, store: Store) -> dict[str, bool]:
    deleted = store.delete_problem(problem_number)

    if deleted is False:
        raise HTTPException(status_code=404, detail="Problem not found")

    return {"deleted": True}


@router.post("/problems/{problem_number}/archive")
def archive_tracked_problem(problem_number: int, store: Store) -> dict[str, bool]:
    res = store.archive_problem(problem_number)

    if res is False:
        raise HTTPException(status_code=404, detail="Problem not found")

    return {"archived": True}


@router.post("/problems/{problem_number}/restore")
def restore_tracked_problem(problem_number: int, store: Store) -> dict[str, bool]:
    res = store.restore_problem(problem_number, date.today())

    if res is False:
        raise HTTPException(status_code=404, detail="Problem not found")

    return {"restored": True}



def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings.from_env()

    @asynccontextmanager
    async def lifespan(application: FastAPI):
        if settings.mode == "hosted":
            application.state.verifier = TokenVerifier(settings.supabase_url)
            application.state.pool = open_pool(settings.database_url)
            try:
                yield
            finally:
                application.state.pool.close()
        else:
            initialize_database(DATABASE_PATH)
            yield

    application = FastAPI(lifespan=lifespan)
    application.state.settings = settings
    if settings.mode == "hosted":
        application.add_middleware(RequestBodyLimitMiddleware, max_body_size=MAX_REQUEST_BYTES)
    # Added last so CORS also wraps body-limit responses from the middleware.
    application.add_middleware(
        CORSMiddleware, allow_origins=list(settings.allowed_origins),
        allow_methods=["GET", "POST", "PUT", "DELETE"],
        allow_headers=["Authorization", "Content-Type"],
    )

    @application.exception_handler(StorageError)
    async def storage_failure(request: Request, error: StorageError):
        if isinstance(error, ProblemLimitExceeded):
            return JSONResponse(status_code=403, content={"detail": str(error)})
        if isinstance(error, ProblemNotFound):
            return JSONResponse(status_code=404, content={"detail": "Problem not found"})
        if isinstance(error, DuplicateProblem):
            return JSONResponse(status_code=409, content={"detail": "Problem already exists"})
        return JSONResponse(status_code=503, content={"detail": "Database temporarily unavailable. Please try again."})

    @application.get("/health")
    def health():
        return {"status": "ok"}

    application.include_router(router)
    return application


app = create_app()
