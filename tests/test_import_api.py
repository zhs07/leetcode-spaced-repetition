"""Read-only previews and validated, transactional Notion imports."""

import csv
import io
import sqlite3
from datetime import date

import pytest
from fastapi.testclient import TestClient

import main
from importing import NOTION_DATA_COLUMNS
from models import Problem, Review
from storage import get_all_problems, get_all_reviews, save_problem, save_review


@pytest.fixture
def import_client(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "DATABASE_PATH", str(tmp_path / "import-test.db"))
    with TestClient(main.app) as client:
        yield client


def test_preview_returns_data_and_row_errors_without_saving(import_client):
    existing = Problem(1, "Existing Two Sum", "Easy", "Arrays", "Keep this note")
    save_problem(main.DATABASE_PATH, existing)
    existing_review = Review(1, date(2026, 9, 1), "Partial Recall")
    save_review(main.DATABASE_PATH, existing_review)

    row = {
        "Problem": "Two Sum #1",
        "Difficulty": "Easy",
        "Topic": "Arrays & Hashing",
        "Last Reviewed": "September 10, 2026",
        "Mastery": "🔵 Mastered",
        "Pattern/Trick": "Hash map, with notes\non two lines",
        "Reviews": "3",
    }
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=NOTION_DATA_COLUMNS)
    writer.writeheader()
    writer.writerows([
        row,
        {**row, "Problem": "Missing Number"},
        {column: "" for column in NOTION_DATA_COLUMNS},
        {**row, "Problem": "Contains Duplicate #217"},
    ])

    response = import_client.post(
        "/imports/notion/preview", json={"csv_text": stream.getvalue()}
    )

    assert response.status_code == 200
    body = response.json()
    assert [item["problem"]["number"] for item in body["problems"]] == [1, 217]
    assert body["problems"][0]["problem"]["notes"] == row["Pattern/Trick"]
    assert body["problems"][0]["problem"]["first_attempt"] == {
        "reviewed_on": "2026-09-10",
        "mastery_level": "Mastered",
    }
    assert body["problems"][0]["total_attempts"] == 3
    assert body["errors"] == [{"row_number": 3, "message": "No match found"}]
    assert body["skipped_rows"] == 1
    assert get_all_problems(main.DATABASE_PATH) == [existing]
    assert get_all_reviews(main.DATABASE_PATH) == [existing_review]


def test_preview_rejects_missing_csv_headers(import_client):
    response = import_client.post(
        "/imports/notion/preview", json={"csv_text": "Problem\nTwo Sum #1\n"}
    )

    assert response.status_code == 400
    assert response.json()["detail"].startswith("Missing columns:")
    assert "Last Reviewed" in response.json()["detail"]
    assert get_all_problems(main.DATABASE_PATH) == []
    assert get_all_reviews(main.DATABASE_PATH) == []


@pytest.mark.parametrize("payload", [{}, {"csv_text": ""}])
def test_preview_rejects_missing_or_empty_request_text(import_client, payload):
    response = import_client.post("/imports/notion/preview", json=payload)
    assert response.status_code == 422


def notion_csv(rows):
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=NOTION_DATA_COLUMNS)
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue()


def notion_row(number=101, **changes):
    return {
        "Problem": f"CSV example #{number}",
        "Difficulty": "Easy",
        "Topic": "Arrays",
        "Last Reviewed": "September 10, 2026",
        "Mastery": "🔵 Mastered",
        "Pattern/Trick": "Keep commas, and\nnewlines",
        "Reviews": "4",
        **changes,
    }


@pytest.mark.parametrize("mastery, exported_interval, next_review", [
    ("🔵 Mastered", "14", "2026-10-10"),
    ("🟢 Solved Independently", "7", "2026-09-24"),
    ("🟡 Solved With Struggle", "3", "2026-09-17"),
])
def test_older_export_intervals_use_current_schedule(
    import_client, mastery, exported_interval, next_review,
):
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(
        stream, fieldnames=[*NOTION_DATA_COLUMNS, "Review Interval (Days)"],
    )
    writer.writeheader()
    writer.writerow({
        **notion_row(Mastery=mastery), "Review Interval (Days)": exported_interval,
    })
    payload = {"csv_text": stream.getvalue()}

    preview = import_client.post("/imports/notion/preview", json=payload)
    assert preview.status_code == 200
    assert preview.json()["errors"] == []
    assert len(preview.json()["problems"]) == 1
    assert get_all_problems(main.DATABASE_PATH) == []

    imported = import_client.post("/imports/notion", json=payload)
    assert imported.status_code == 200
    assert imported.json()["imported_numbers"] == [101]
    summary = import_client.get("/problems/summary").json()[0]
    assert summary["next_review"] == next_review
    assert summary["attempts"] == 4
    assert len(get_all_reviews(main.DATABASE_PATH)) == 1


def test_confirm_import_saves_valid_rows_and_repeat_preserves_counts(import_client):
    existing = Problem(101, "Existing name", "Hard", "Graphs", "Existing notes")
    save_problem(main.DATABASE_PATH, existing)
    review = Review(101, date(2026, 9, 1), "Partial Recall")
    save_review(main.DATABASE_PATH, review)
    text = notion_csv([
        notion_row(), notion_row(102),
        notion_row(103, Problem="Missing number"),
        {column: "" for column in NOTION_DATA_COLUMNS},
    ])

    response = import_client.post("/imports/notion", json={"csv_text": text})

    assert response.status_code == 200
    assert response.json() == {
        "imported_numbers": [102], "skipped_existing_numbers": [101],
        "errors": [{"row_number": 4, "message": "No match found"}], "skipped_rows": 1,
    }
    assert get_all_problems(main.DATABASE_PATH) == [
        existing,
        Problem(102, "CSV example", "Easy", "Arrays", "Keep commas, and\nnewlines",
                historical_attempts=3),
    ]
    before_reviews = get_all_reviews(main.DATABASE_PATH)
    assert before_reviews == [review, Review(102, date(2026, 9, 10), "Mastered")]
    summaries = import_client.get("/problems/summary").json()
    assert summaries[1]["attempts"] == 4
    assert summaries[1]["next_review"] == "2026-10-10"

    repeated = import_client.post("/imports/notion", json={"csv_text": text})
    assert repeated.json()["imported_numbers"] == []
    assert repeated.json()["skipped_existing_numbers"] == [101, 102]
    assert get_all_reviews(main.DATABASE_PATH) == before_reviews
    assert import_client.get("/problems/summary").json() == summaries


@pytest.mark.parametrize("path", ["/imports/notion/preview", "/imports/notion"])
def test_malformed_csv_rejects_file_without_writes(import_client, path):
    text = ",".join(NOTION_DATA_COLUMNS) + '\n"unterminated quote'
    response = import_client.post(path, json={"csv_text": text})
    assert response.status_code == 400
    assert response.json()["detail"].startswith("Malformed CSV:")
    assert get_all_problems(main.DATABASE_PATH) == []
    assert get_all_reviews(main.DATABASE_PATH) == []


@pytest.mark.parametrize("payload", [{}, {"csv_text": ""}, {"problems": []}])
def test_confirm_requires_original_csv(import_client, payload):
    response = import_client.post("/imports/notion", json=payload)
    assert response.status_code == 422
    assert get_all_problems(main.DATABASE_PATH) == []


def test_confirmation_revalidates_changed_csv_and_accepts_utf8_bom(import_client):
    valid = notion_csv([notion_row()])
    preview = import_client.post("/imports/notion/preview", json={"csv_text": valid})
    assert preview.json()["problems"][0]["total_attempts"] == 4

    changed = notion_csv([notion_row(Reviews="0")])
    rejected = import_client.post("/imports/notion", json={"csv_text": changed})
    assert rejected.status_code == 200
    assert rejected.json()["imported_numbers"] == []
    assert len(rejected.json()["errors"]) == 1
    assert get_all_problems(main.DATABASE_PATH) == []

    imported = import_client.post("/imports/notion", json={"csv_text": "\ufeff" + valid})
    assert imported.status_code == 200
    assert imported.json()["imported_numbers"] == [101]


def test_confirmation_database_failure_rolls_back_and_reports_failure(import_client):
    with sqlite3.connect(main.DATABASE_PATH) as connection:
        connection.executescript("""
            CREATE TRIGGER fail_import_review
            BEFORE INSERT ON reviews WHEN NEW.problem_number = 102
            BEGIN
                SELECT RAISE(ABORT, 'forced API import failure');
            END;
        """)

    response = import_client.post("/imports/notion", json={
        "csv_text": notion_csv([notion_row(101), notion_row(102)]),
    })

    assert response.status_code == 500
    assert response.json() == {"detail": "Import failed. No problems were saved. Please try again."}
    assert get_all_problems(main.DATABASE_PATH) == []
    assert get_all_reviews(main.DATABASE_PATH) == []
