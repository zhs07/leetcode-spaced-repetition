"""Blind practice selection, statement caching, and normal attempt persistence."""

from datetime import date

import pytest
from fastapi.testclient import TestClient

import main
from models import Problem, Review
from statements import StatementUnavailable
from storage import (
    archive_problem, restore_problem, get_all_problems, get_all_reviews,
    get_problem_statement, save_problem, save_review, save_problem_statement,
)


@pytest.fixture
def practice_client(tmp_path, monkeypatch):
    class FixedDate(date):
        @classmethod
        def today(cls):
            return date(2026, 10, 1)

    monkeypatch.setattr(main, "DATABASE_PATH", str(tmp_path / "practice.db"))
    monkeypatch.setattr(main, "date", FixedDate)
    monkeypatch.setattr(main, "fetch_statement", lambda number: ("<p>A sequence of values.</p><pre>Input: [1,2]</pre>", f"example-{number}"))
    with TestClient(main.app) as client:
        yield client


def seed(number, reviewed_on=None, historical_attempts=0):
    problem = Problem(number, f"Hidden name {number}", "Easy", "Hidden topic", "Hidden solution",
                      historical_attempts=historical_attempts)
    save_problem(main.DATABASE_PATH, problem)
    if reviewed_on:
        save_review(main.DATABASE_PATH, Review(number, reviewed_on, "Mastered"))


def test_random_pick_uses_only_saved_due_active_problems_without_recording_attempt(practice_client, monkeypatch):
    seed(1, date(2026, 8, 31))  # Overdue.
    seed(2, date(2026, 9, 1))  # Exactly due today.
    seed(3, date(2026, 10, 1))  # Future review.
    seed(4, date(2026, 9, 1))
    archive_problem(main.DATABASE_PATH, 4)
    seed(5)  # Unreviewed is not automatically due.
    seed(6, historical_attempts=3)  # A count alone creates no schedule.
    seed(7)
    archive_problem(main.DATABASE_PATH, 7)
    restore_problem(main.DATABASE_PATH, 7, date(2026, 10, 1))
    before_problems, before_reviews = get_all_problems(main.DATABASE_PATH), get_all_reviews(main.DATABASE_PATH)

    def choose(candidates):
        assert {problem.number for problem in candidates} == {1, 2, 7}
        return next(problem for problem in candidates if problem.number == 2)

    monkeypatch.setattr(main, "choice", choose)
    response = practice_client.post("/practice/random")
    assert response.status_code == 200
    body = response.json()
    assert body["problem_number"] == 2
    assert body["statement"][0]["tag"] == "p"
    assert body["statement"][1]["tag"] == "pre"
    assert not {"name", "topic", "difficulty", "notes", "mastery_level", "attempts"} & body.keys()
    assert "Hidden" not in str(body)
    assert get_all_problems(main.DATABASE_PATH) == before_problems
    assert get_all_reviews(main.DATABASE_PATH) == before_reviews


def test_cached_statement_survives_reload_without_network(practice_client, monkeypatch):
    seed(1, date(2026, 9, 1))
    first = practice_client.post("/practice/random").json()
    assert get_problem_statement(main.DATABASE_PATH, 1) is not None

    def no_network(number):
        pytest.fail("Cached statements must not fetch again")

    monkeypatch.setattr(main, "fetch_statement", no_network)
    assert practice_client.post("/practice/random").json() == first
    assert practice_client.post("/practice/1/statement/load").json() == first


def test_no_due_problems_does_not_fetch_or_create_attempts(practice_client, monkeypatch):
    seed(1, date(2026, 10, 1))
    seed(2)
    seed(3, date(2026, 9, 1))
    archive_problem(main.DATABASE_PATH, 3)
    monkeypatch.setattr(main, "fetch_statement", lambda number: pytest.fail("Nothing should be fetched"))
    before = get_all_reviews(main.DATABASE_PATH)
    response = practice_client.post("/practice/random")
    assert response.status_code == 404
    assert "no due or overdue" in response.json()["detail"]
    assert get_all_reviews(main.DATABASE_PATH) == before


def test_failed_fetch_keeps_selection_and_manual_fallback_is_cached(practice_client, monkeypatch):
    seed(1, date(2026, 9, 1))

    def unavailable(number):
        raise StatementUnavailable("Statement unavailable", "example-1")

    monkeypatch.setattr(main, "fetch_statement", unavailable)
    response = practice_client.post("/practice/random")
    assert response.status_code == 200
    assert response.json()["problem_number"] == 1
    assert response.json()["statement"] is None
    assert response.json()["statement_error"] == "Statement unavailable"
    assert get_problem_statement(main.DATABASE_PATH, 1) is None

    text = 'A pasted statement.\nInput: <script>alert("x")</script>'
    saved = practice_client.put("/practice/1/statement", json={"text": text})
    assert saved.status_code == 200
    assert saved.json()["statement"][0]["tag"] == "pre"
    assert saved.json()["statement"][0]["children"] == [text]
    assert saved.json()["statement_error"] is None
    assert practice_client.post("/practice/random").json() == saved.json()
    assert len(get_all_reviews(main.DATABASE_PATH)) == 1


@pytest.mark.parametrize("text", ["", "   ", "x" * 100001])
def test_pasted_statement_requires_nonempty_bounded_text(practice_client, text):
    seed(1)
    response = practice_client.put("/practice/1/statement", json={"text": text})
    assert response.status_code == 422
    assert get_problem_statement(main.DATABASE_PATH, 1) is None


def test_recording_blind_attempt_updates_correct_problem_and_normal_schedule(practice_client):
    seed(1, date(2026, 9, 1), historical_attempts=3)
    assert practice_client.post("/practice/random").json()["problem_number"] == 1
    response = practice_client.post("/reviews", json={
        "problem_number": 1, "reviewed_on": "2026-10-01", "mastery_level": "Solved Independently",
    })
    assert response.status_code == 201
    summary = practice_client.get("/problems/1/summary").json()
    assert summary["attempts"] == 5
    assert summary["next_review"] == "2026-10-15"
    assert summary["name"] == "Hidden name 1"
    assert practice_client.post("/practice/random").status_code == 404


def test_deleting_problem_removes_cached_statement(practice_client):
    seed(1)
    save_problem_statement(main.DATABASE_PATH, 1, "<p>Cached statement</p>", "example-1")
    assert practice_client.delete("/problems/1").status_code == 200
    assert get_problem_statement(main.DATABASE_PATH, 1) is None
    assert practice_client.post("/practice/1/statement/load").status_code == 404
    assert practice_client.put("/practice/1/statement", json={"text": "Missing problem"}).status_code == 404
    assert practice_client.get("/problems/1/summary").status_code == 404
