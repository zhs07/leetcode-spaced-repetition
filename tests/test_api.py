from fastapi.testclient import TestClient
import pytest

import main
from models import Problem, Review
from datetime import date
from storage import (
    initialize_database,
    save_problem,
    get_all_reviews,
    get_all_problems,
    save_review,
)


def test_post_review_saves_valid_attempt(tmp_path, monkeypatch):
    database_path = str(tmp_path / "test.db")
    initialize_database(database_path)

    problem = Problem(
        number=1,
        name="Two Sum",
        difficulty="Easy",
        topic="Arrays & Hashing",
        notes="",
    )
    save_problem(database_path, problem)

    monkeypatch.setattr(main, "DATABASE_PATH", database_path)

    payload = {
        "problem_number": 1,
        "reviewed_on": "2026-09-20",
        "mastery_level": "Solved Independently",
    }

    with TestClient(main.app) as client:
        response = client.post("/reviews", json=payload)

    assert response.status_code == 201
    assert response.json() == payload
    assert get_all_reviews(database_path) == [
        Review(
            problem_number=1,
            reviewed_on=date(2026, 9, 20),
            mastery_level="Solved Independently",
        )
    ]


def test_post_problem_saves_valid_problem(tmp_path, monkeypatch):
    database_path = str(tmp_path / "test.db")
    initialize_database(database_path)
    monkeypatch.setattr(main, "DATABASE_PATH", database_path)

    payload = {
        "number": 1,
        "name": " Two Sum ",
        "difficulty": "Easy",
        "topic": "Arrays & Hashing",
    }

    expected = {
        "number": 1,
        "name": "Two Sum",
        "difficulty": "Easy",
        "topic": "Arrays & Hashing",
        "notes": "",
        "archived": False,
        "review_due_on": None,
        "historical_attempts": 0,
    }

    with TestClient(main.app) as client:
        response = client.post("/problems", json=payload)

    assert response.status_code == 201
    assert response.json() == expected
    assert get_all_problems(database_path) == [
        Problem(
            number=1,
            name="Two Sum",
            difficulty="Easy",
            topic="Arrays & Hashing",
            notes="",
        )
    ]


def test_post_duplicate_problem_returns_conflict(tmp_path, monkeypatch):
    database_path = str(tmp_path / "test.db")
    initialize_database(database_path)
    monkeypatch.setattr(main, "DATABASE_PATH", database_path)

    payload = {
        "number": 1,
        "name": " Two Sum ",
        "difficulty": "Easy",
        "topic": "Arrays & Hashing",
    }

    with TestClient(main.app) as client:
        first_response = client.post("/problems", json=payload)
        second_response = client.post("/problems", json=payload)

    assert first_response.status_code == 201
    assert second_response.status_code == 409
    assert second_response.json() == {"detail": "Problem already exists"}
    assert get_all_problems(database_path) == [
        Problem(
            number=1,
            name="Two Sum",
            difficulty="Easy",
            topic="Arrays & Hashing",
            notes="",
        )
    ]


def test_startup_initializes_database(tmp_path, monkeypatch):
    database_path = tmp_path / "test.db"
    monkeypatch.setattr(main, "DATABASE_PATH", str(database_path))

    assert not database_path.exists()

    with TestClient(main.app) as client:
        problems_response = client.get("/problems")
        reviews_response = client.get("/reviews")

    assert database_path.exists()
    assert problems_response.status_code == 200
    assert problems_response.json() == []
    assert reviews_response.status_code == 200
    assert reviews_response.json() == []


def test_problem_summaries_include_reviewed_and_unreviewed(tmp_path, monkeypatch):
    database_path = tmp_path / "test.db"
    monkeypatch.setattr(main, "DATABASE_PATH", str(database_path))

    with TestClient(main.app) as client:
        problem_one = Problem(1, "Two sum", "Easy", "Arrays & Hashing", "")
        problem_two = Problem(206, "Reverse Linked List", "Easy", "Linked List", "")

        save_problem(database_path, problem_one)
        save_problem(database_path, problem_two)

        review_solved_independently = Review(
            1, date(2026, 9, 20), "Solved Independently"
        )
        review_partial_recall = Review(1, date(2026, 9, 22), "Partial Recall")

        save_review(database_path, review_solved_independently)
        save_review(database_path, review_partial_recall)

        response = client.get("/problems/summary")
        summaries = response.json()

    assert len(summaries) == 2
    assert response.status_code == 200
    by_number = {}
    for summary in summaries:
        by_number[summary["number"]] = summary

    assert by_number[1]["mastery_level"] == "Partial Recall"
    assert by_number[1]["next_review"] == "2026-09-25"
    assert by_number[1]["attempts"] == 2

    assert by_number[206]["mastery_level"] is None
    assert by_number[206]["next_review"] is None
    assert by_number[206]["attempts"] == 0


def test_post_problem_with_first_attempt(tmp_path, monkeypatch):
    database_path = str(tmp_path / "test.db")
    monkeypatch.setattr(main, "DATABASE_PATH", database_path)

    payload = {
        "number": 1,
        "name": "Two Sum",
        "difficulty": "Easy",
        "topic": "Arrays & Hashing",
        "first_attempt": {
            "reviewed_on": "2026-09-29",
            "mastery_level": "Partial Recall",
        },
    }

    with TestClient(main.app) as client:
        response = client.post("/problems", json=payload)
        summary_response = client.get("/problems/summary")

    assert response.status_code == 201
    assert summary_response.status_code == 200

    assert get_all_reviews(database_path) == [
        Review(1, date(2026, 9, 29), "Partial Recall")
    ]

    assert summary_response.json() == [
        {
            "number": 1,
            "name": "Two Sum",
            "difficulty": "Easy",
            "topic": "Arrays & Hashing",
            "next_review": "2026-10-02",
            "mastery_level": "Partial Recall",
            "notes": "",
            "attempts": 1,
            "archived": False
        }
    ]
    
def test_delete_problem_removes_problem_and_reviews(tmp_path, monkeypatch):
    database_path = str(tmp_path / "test.db")
    monkeypatch.setattr(main, "DATABASE_PATH", database_path)

    with TestClient(main.app) as client:
        problem = Problem(
            number=1,
            name="Two Sum",
            difficulty="Easy",
            topic="Arrays & Hashing",
            notes="",
        )
        review = Review(
            problem_number=1,
            reviewed_on=date(2026, 9, 29),
            mastery_level="Partial Recall",
        )

        save_problem(database_path, problem)
        save_review(database_path, review)

        response = client.delete("/problems/1")


    assert response.status_code == 200
    assert response.json() == {"deleted" : True}
    assert get_all_reviews(database_path) == []
    assert get_all_problems(database_path) == []
    
def test_delete_missing_problem_returns_404(tmp_path, monkeypatch):
    database_path = str(tmp_path / "test.db")
    monkeypatch.setattr(main, "DATABASE_PATH", database_path)

    with TestClient(main.app) as client:
        response = client.delete("/problems/999")

    assert response.status_code == 404
    assert response.json() == {"detail": "Problem not found"}


@pytest.mark.parametrize("has_history", [False, True])
def test_archive_restore_and_practice_flow(tmp_path, monkeypatch, has_history):
    class FixedDate(date):
        @classmethod
        def today(cls):
            return date(2026, 9, 30)

    database_path = str(tmp_path / "test.db")
    monkeypatch.setattr(main, "DATABASE_PATH", database_path)
    monkeypatch.setattr(main, "date", FixedDate)
    payload = {
        "number": 1,
        "name": "Two Sum",
        "difficulty": "Easy",
        "topic": "Arrays & Hashing",
        "notes": "Keep my approach",
    }
    if has_history:
        payload["first_attempt"] = {
            "reviewed_on": "2026-09-29",
            "mastery_level": "Mastered",
        }

    with TestClient(main.app) as client:
        assert client.post("/problems", json=payload).status_code == 201
        other = {"number": 217, "name": "Contains Duplicate", "difficulty": "Easy", "topic": "Arrays"}
        assert client.post("/problems", json=other).status_code == 201
        original_reviews = client.get("/reviews").json()
        for _ in range(2):
            archived = client.post("/problems/1/archive")
            assert archived.status_code == 200
            assert archived.json() == {"archived": True}
        summaries = client.get("/problems/summary").json()
        assert summaries[0]["archived"] is True
        assert summaries[0]["next_review"] is None
        assert summaries[0]["notes"] == payload["notes"]
        assert summaries[0]["attempts"] == int(has_history)
        assert summaries[0]["mastery_level"] == ("Mastered" if has_history else None)
        assert summaries[1]["archived"] is False
        assert client.get("/problems/due").json() == []
        assert client.get("/reviews").json() == original_reviews

        for _ in range(2):
            restored = client.post("/problems/1/restore")
            assert restored.status_code == 200
            assert restored.json() == {"restored": True}
        summary = client.get("/problems/summary").json()[0]
        assert summary["archived"] is False
        assert summary["next_review"] == "2026-09-30"
        assert summary["attempts"] == int(has_history)
        assert [p["number"] for p in client.get("/problems/due").json()] == [1]
        assert client.get("/reviews").json() == original_reviews

        attempt = {"problem_number": 1, "reviewed_on": "2026-09-30", "mastery_level": "Solved Independently"}
        assert client.post("/reviews", json=attempt).status_code == 201
        # A repeated restore of an active problem must preserve its new schedule.
        assert client.post("/problems/1/restore").json() == {"restored": True}
        summary = client.get("/problems/summary").json()[0]
        assert summary["next_review"] == "2026-10-14"
        assert summary["attempts"] == int(has_history) + 1
        assert summary["mastery_level"] == "Solved Independently"
        assert client.get("/reviews").json() == original_reviews + [attempt]
        assert client.get("/problems/due").json() == []
        assert get_all_problems(database_path)[0].review_due_on is None


@pytest.mark.parametrize("action", ["archive", "restore"])
def test_archive_and_restore_missing_problem_return_404(tmp_path, monkeypatch, action):
    database_path = str(tmp_path / "test.db")
    monkeypatch.setattr(main, "DATABASE_PATH", database_path)
    with TestClient(main.app) as client:
        response = client.post(f"/problems/999/{action}")
    assert response.status_code == 404
    assert response.json() == {"detail": "Problem not found"}
    assert get_all_problems(database_path) == []
    assert get_all_reviews(database_path) == []
