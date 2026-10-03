"""Size limits on new input; all storage is disposable or replaced by a spy."""

import asyncio
import csv
import io
import json

from fastapi.testclient import TestClient
import pytest

import main
from importing import NOTION_DATA_COLUMNS
from input_limits import MAX_CSV_CHARACTERS, MAX_NAME_CHARACTERS, MAX_NOTES_CHARACTERS, MAX_REQUEST_BYTES, MAX_TOPIC_CHARACTERS
from models import Problem
from settings import Settings
from storage import save_problem


PAYLOAD = {"number": 1, "name": "Example", "difficulty": "Easy", "topic": "Arrays", "notes": "Keep me"}


@pytest.fixture
def input_client(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "DATABASE_PATH", str(tmp_path / "input-limits.db"))
    with TestClient(main.create_app(Settings())) as client:
        yield client


def test_unicode_fields_exactly_at_the_limits_save_without_truncation(input_client):
    payload = {**PAYLOAD, "name": "名" * MAX_NAME_CHARACTERS,
               "topic": "題" * MAX_TOPIC_CHARACTERS, "notes": "🚀" * MAX_NOTES_CHARACTERS}
    response = input_client.post("/problems", json=payload)
    assert response.status_code == 201
    for field in ("name", "topic", "notes"):
        assert response.json()[field] == payload[field]


@pytest.mark.parametrize("field, maximum", [
    ("name", MAX_NAME_CHARACTERS), ("topic", MAX_TOPIC_CHARACTERS), ("notes", MAX_NOTES_CHARACTERS),
])
def test_oversized_field_rejects_problem_and_first_attempt_without_changing_history(input_client, field, maximum):
    assert input_client.post("/problems", json=PAYLOAD).status_code == 201
    before = input_client.get("/problems").json(), input_client.get("/reviews").json()
    payload = {**PAYLOAD, "number": 2, field: "x" * (maximum + 1),
               "first_attempt": {"reviewed_on": "2026-10-03", "mastery_level": "Mastered"}}
    response = input_client.post("/problems", json=payload)
    assert response.status_code == 422
    assert any(error["loc"] == ["body", field] for error in response.json()["detail"])
    assert (input_client.get("/problems").json(), input_client.get("/reviews").json()) == before


def test_csv_cannot_bypass_new_note_limit_and_keeps_valid_row_import_behavior(input_client):
    row = {"Problem": "Valid #1", "Difficulty": "Easy", "Topic": "Arrays",
           "Last Reviewed": "October 3, 2026", "Mastery": "🔵 Mastered",
           "Pattern/Trick": "Valid note", "Reviews": "3"}
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=NOTION_DATA_COLUMNS)
    writer.writeheader()
    writer.writerows([row, {**row, "Problem": "Oversized #2", "Pattern/Trick": "x" * (MAX_NOTES_CHARACTERS + 1)}])
    payload = {"csv_text": stream.getvalue()}
    preview = input_client.post("/imports/notion/preview", json=payload)
    assert preview.status_code == 200
    assert [item["problem"]["number"] for item in preview.json()["problems"]] == [1]
    assert preview.json()["errors"][0]["row_number"] == 3
    assert "notes" in preview.json()["errors"][0]["message"]
    result = input_client.post("/imports/notion", json=payload)
    assert result.status_code == 200
    assert result.json()["imported_numbers"] == [1]
    assert len(input_client.get("/reviews").json()) == 1


def test_existing_large_records_remain_readable(input_client):
    problem = Problem(1, "n" * (MAX_NAME_CHARACTERS + 1), "Easy", "Arrays", "x" * (MAX_NOTES_CHARACTERS + 1))
    save_problem(main.DATABASE_PATH, problem)
    response = input_client.get("/problems/summary")
    assert response.status_code == 200
    assert response.json()[0]["name"] == problem.name
    assert response.json()[0]["notes"] == problem.notes


@pytest.mark.parametrize("path", ["/imports/notion/preview", "/imports/notion"])
def test_csv_text_size_limit_is_checked_before_parsing_or_saving(input_client, path):
    response = input_client.post(path, json={"csv_text": "x" * (MAX_CSV_CHARACTERS + 1)})
    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == ["body", "csv_text"]
    assert input_client.get("/problems").json() == []
    assert input_client.get("/reviews").json() == []


def transport_app():
    # No lifespan is run here and the store is replaced: these checks exercise
    # the real hosted middleware/route configuration without a DB or provider.
    saved = []

    class SpyStore:
        def save_problem_with_first_attempt(self, problem, first_attempt):
            saved.append(problem)

    app = main.create_app(Settings(
        mode="hosted", database_url="postgresql://test@localhost/test",
        supabase_url="https://test.supabase.co", allowed_origins=("https://tracker.example",),
    ))
    app.dependency_overrides[main.get_store] = lambda: SpyStore()
    return app, saved


@pytest.mark.parametrize("extra, expected_status", [(0, 201), (1, 413)])
def test_raw_request_byte_boundary_and_cors(extra, expected_status):
    app, saved = transport_app()
    body = json.dumps(PAYLOAD).encode()
    body += b" " * (MAX_REQUEST_BYTES + extra - len(body))
    client = TestClient(app)
    try:
        response = client.post("/problems", content=body, headers={
            "Content-Type": "application/json", "Origin": "https://tracker.example",
        })
        assert response.status_code == expected_status
        assert response.headers["access-control-allow-origin"] == "https://tracker.example"
        assert len(saved) == (1 if expected_status == 201 else 0)
    finally:
        client.close()


@pytest.mark.parametrize("length_header", [None, b"1"])
def test_streamed_oversized_request_cannot_bypass_limit(length_header):
    app, saved = transport_app()
    body = json.dumps(PAYLOAD).encode()
    body += b" " * (MAX_REQUEST_BYTES + 1 - len(body))
    chunks = iter([body[:500_000], body[500_000:1_000_000], body[1_000_000:]])
    sent = []
    headers = [(b"content-type", b"application/json"), (b"origin", b"https://tracker.example")]
    if length_header is not None:
        headers.append((b"content-length", length_header))
    scope = {"type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1",
             "method": "POST", "scheme": "https", "path": "/problems", "raw_path": b"/problems",
             "query_string": b"", "root_path": "", "headers": headers,
             "client": ("127.0.0.1", 1234), "server": ("tracker.example", 443)}

    async def receive():
        chunk = next(chunks)
        return {"type": "http.request", "body": chunk, "more_body": len(chunk) == 500_000}

    async def send(message):
        sent.append(message)

    asyncio.run(app(scope, receive, send))
    response = next(message for message in sent if message["type"] == "http.response.start")
    assert response["status"] == 413
    assert (b"access-control-allow-origin", b"https://tracker.example") in response["headers"]
    assert saved == []
