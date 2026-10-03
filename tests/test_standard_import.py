"""Standard CSV contract, read-only previews, and disposable SQLite saves."""

import csv
import io
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import main
from importing import STANDARD_OPTIONAL_COLUMNS, STANDARD_REQUIRED_COLUMNS, preview_standard_csv
from input_limits import MAX_CSV_CHARACTERS, MAX_NOTES_CHARACTERS
from scheduler import REVIEW_INTERVALS
from storage import get_all_problems, get_all_reviews


def row(number=1, **changes):
    return {"number": str(number), "name": "Two Sum", "difficulty": "Easy", "topic": "Arrays", **changes}


def csv_text(rows, headers=(*STANDARD_REQUIRED_COLUMNS, *STANDARD_OPTIONAL_COLUMNS)):
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=headers)
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue()


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "DATABASE_PATH", str(tmp_path / "standard-import.db"))
    with TestClient(main.app) as test_client:
        yield test_client


def test_minimal_import_preview_save_repeat_and_first_real_attempt(client):
    payload = {"csv_text": csv_text([row()], STANDARD_REQUIRED_COLUMNS)}
    preview = client.post("/imports/standard/preview", json=payload)
    assert preview.status_code == 200
    item = preview.json()["problems"][0]
    assert item["total_attempts"] == 0
    assert item["problem"]["first_attempt"] is None
    assert item["problem"]["notes"] == ""
    assert get_all_problems(main.DATABASE_PATH) == get_all_reviews(main.DATABASE_PATH) == []

    assert client.post("/imports/standard", json=payload).json()["imported_numbers"] == [1]
    summary = client.get("/problems/1/summary").json()
    assert (summary["attempts"], summary["mastery_level"], summary["next_review"]) == (0, None, None)
    assert get_all_reviews(main.DATABASE_PATH) == []
    assert client.post("/imports/standard", json=payload).json()["skipped_existing_numbers"] == [1]
    assert client.post("/reviews", json={
        "problem_number": 1, "reviewed_on": "2026-10-03", "mastery_level": "Partial Recall",
    }).status_code == 201
    summary = client.get("/problems/1/summary").json()
    assert summary["attempts"] == 1
    assert summary["next_review"] == "2026-10-06"


@pytest.mark.parametrize("mastery, interval", REVIEW_INTERVALS.items())
def test_all_mastery_levels_default_to_one_review(client, mastery, interval):
    from datetime import date, timedelta
    payload = {"csv_text": csv_text([row(reviewed_on="2026-10-03", mastery_level=mastery)])}
    result = client.post("/imports/standard", json=payload)
    assert result.json()["errors"] == []
    summary = client.get("/problems/1/summary").json()
    assert summary["attempts"] == 1
    assert summary["next_review"] == (date(2026, 10, 3) + timedelta(days=interval)).isoformat()
    assert len(get_all_reviews(main.DATABASE_PATH)) == 1


def test_mixed_batch_preserves_counts_notes_and_existing_data(client):
    assert client.post("/problems", json={
        "number": 1, "name": "Keep existing", "difficulty": "Hard", "topic": "Graphs", "notes": "Keep notes",
    }).status_code == 201
    text = csv_text([
        row(), row(2, notes='Comma, quotes "and"\nnewlines', reviewed_on="2026-10-03",
                   mastery_level="Mastered", total_attempts="4"),
        row(3), row(number="missing"), row(2),
        {column: "" for column in (*STANDARD_REQUIRED_COLUMNS, *STANDARD_OPTIONAL_COLUMNS)},
    ])
    result = client.post("/imports/standard", json={"csv_text": text}).json()
    assert result["imported_numbers"] == [2, 3]
    assert result["skipped_existing_numbers"] == [1]
    assert [error["row_number"] for error in result["errors"]] == [5, 6]
    assert result["skipped_rows"] == 1
    assert client.get("/problems/1/summary").json()["notes"] == "Keep notes"
    summary = client.get("/problems/2/summary").json()
    assert summary["attempts"] == 4
    assert summary["notes"] == 'Comma, quotes "and"\nnewlines'
    before = client.get("/problems/summary").json()
    client.post("/imports/standard", json={"csv_text": text})
    assert client.get("/problems/summary").json() == before
    assert len(get_all_reviews(main.DATABASE_PATH)) == 1


@pytest.mark.parametrize("changes, message", [
    ({"reviewed_on": "2026-10-03"}, "Provide both"),
    ({"mastery_level": "Mastered"}, "Provide both"),
    ({"total_attempts": "1"}, "Positive total_attempts requires"),
    ({"total_attempts": "-1"}, "nonnegative integer"),
    ({"total_attempts": "1.5"}, "nonnegative integer"),
    ({"number": ""}, "positive integer"),
    ({"number": "0"}, "positive integer"),
    ({"number": "1.0"}, "positive integer"),
    ({"name": " "}, "must not be blank"),
    ({"topic": " "}, "must not be blank"),
    ({"difficulty": "Unknown"}, "Input should be"),
    ({"notes": "x" * (MAX_NOTES_CHARACTERS + 1)}, "at most"),
    ({"reviewed_on": "2026-10-03", "mastery_level": "Mastered", "total_attempts": "0"}, "at least one"),
    ({"reviewed_on": "20261003", "mastery_level": "Mastered"}, "YYYY-MM-DD"),
    ({"reviewed_on": "2026-02-30", "mastery_level": "Mastered"}, "valid YYYY-MM-DD"),
    ({"reviewed_on": "2026-10-03", "mastery_level": "Unknown"}, "Invalid mastery level"),
])
def test_invalid_rows_are_errors_without_writes(client, changes, message):
    payload = {"csv_text": csv_text([row(**changes)])}
    for endpoint in ("/imports/standard/preview", "/imports/standard"):
        result = client.post(endpoint, json=payload)
        assert result.status_code == 200
        assert message in result.json()["errors"][0]["message"]
    assert get_all_problems(main.DATABASE_PATH) == get_all_reviews(main.DATABASE_PATH) == []


def test_bom_reordered_headers_unknown_columns_and_zero_count():
    text = csv_text([row(extra="ignored", total_attempts="0")],
                    ("topic", "name", "number", "extra", "difficulty", "total_attempts"))
    preview = preview_standard_csv("\ufeff" + text)
    assert preview.errors == []
    assert preview.problems[0].total_attempts == 0


@pytest.mark.parametrize("text, message", [
    ("name,difficulty,topic\nTwo Sum,Easy,Arrays", "Missing columns: number"),
    ("number,name,difficulty,topic,number\n1,Two Sum,Easy,Arrays,1", "duplicate column headers"),
    ('number,name,difficulty,topic\n"unterminated', "Malformed CSV"),
])
def test_invalid_files_rejected_before_writes(client, text, message):
    for endpoint in ("/imports/standard/preview", "/imports/standard"):
        result = client.post(endpoint, json={"csv_text": text})
        assert result.status_code == 400
        assert message in result.json()["detail"]
    assert get_all_problems(main.DATABASE_PATH) == []


def test_wrong_cell_counts_are_row_errors():
    preview = preview_standard_csv("number,name,difficulty,topic\n1,Two Sum,Easy\n2,Two Sum,Easy,Arrays,extra")
    assert preview.problems == []
    assert [error.row_number for error in preview.errors] == [2, 3]


@pytest.mark.parametrize("endpoint", ["/imports/standard/preview", "/imports/standard"])
@pytest.mark.parametrize("payload", [{}, {"csv_text": ""}, {"csv_text": "x" * (MAX_CSV_CHARACTERS + 1)}])
def test_request_limits_apply_to_standard_import(client, endpoint, payload):
    assert client.post(endpoint, json=payload).status_code == 422


def test_template_is_valid_and_demonstrates_both_history_cases():
    template = Path(__file__).parents[1] / "frontend/public/standard-import-template.csv"
    preview = preview_standard_csv(template.read_text())
    assert preview.errors == []
    assert [item.total_attempts for item in preview.problems] == [0, 3]
