"""Real request shapes, external failures, and safe statement formatting."""

import json

import httpx
import pytest

import statements
from schemas import StatementElement


@pytest.fixture(autouse=True)
def clear_catalog_cache():
    statements._problem_catalog.cache_clear()
    yield
    statements._problem_catalog.cache_clear()


def mock_http(monkeypatch, handler):
    real_client = httpx.Client
    transport = httpx.MockTransport(handler)
    monkeypatch.setattr(statements.httpx, "Client", lambda **kwargs: real_client(transport=transport, **kwargs))


def directory(paid=False):
    return {"stat_status_pairs": [{"stat": {"frontend_question_id": 1, "question__title_slug": "two-sum"}, "paid_only": paid}]}


def question(**changes):
    return {"data": {"question": {
        "questionFrontendId": "1", "titleSlug": "two-sum", "content": "<p>A statement.</p>", "isPaidOnly": False,
        **changes,
    }}}


def test_fetch_uses_number_mapping_and_only_requests_selected_description(monkeypatch):
    requests = []

    def handler(request):
        requests.append(request)
        if request.method == "GET":
            assert request.url.path == "/api/problems/all/"
            return httpx.Response(200, json=directory())
        assert request.url.path == "/graphql/"
        body = json.loads(request.content)
        assert body["variables"] == {"slug": "two-sum"}
        assert "content" in body["query"]
        return httpx.Response(200, json=question())

    mock_http(monkeypatch, handler)
    assert statements.fetch_statement(1) == ("<p>A statement.</p>", "two-sum")
    assert statements.fetch_statement(1) == ("<p>A statement.</p>", "two-sum")
    assert [request.method for request in requests] == ["GET", "POST", "POST"]


def test_paid_statement_is_reported_without_requesting_protected_content(monkeypatch):
    requests = []
    mock_http(monkeypatch, lambda request: (requests.append(request) or httpx.Response(200, json=directory(paid=True))))
    with pytest.raises(statements.StatementUnavailable, match="Premium") as error:
        statements.fetch_statement(1)
    assert error.value.slug == "two-sum"
    assert [request.method for request in requests] == ["GET"]


@pytest.mark.parametrize("response", [
    question(questionFrontendId="2"), question(titleSlug="another-problem"),
    question(content=None), question(content="<script>secret()</script>"),
    {"data": None, "errors": [{"message": "Unavailable"}]}, {"data": []},
])
def test_unexpected_or_empty_statement_never_returns_wrong_problem(monkeypatch, response):
    mock_http(monkeypatch, lambda request: httpx.Response(200, json=directory() if request.method == "GET" else response))
    with pytest.raises(statements.StatementUnavailable):
        statements.fetch_statement(1)


@pytest.mark.parametrize("failure", ["timeout", "403", "429", "invalid-json"])
def test_fetch_failures_have_neutral_retry_messages(monkeypatch, failure):
    def handler(request):
        if failure == "timeout":
            raise httpx.ReadTimeout("Timed out", request=request)
        if failure == "invalid-json":
            return httpx.Response(200, text="not JSON")
        return httpx.Response(int(failure))

    mock_http(monkeypatch, handler)
    with pytest.raises(statements.StatementUnavailable, match="Retry, or paste"):
        statements.fetch_statement(1)


def test_formatting_is_preserved_and_scripts_attributes_links_and_untrusted_images_are_removed():
    nodes = statements.parse_statement('''
        <p onclick="bad()">Use <code>nums</code> &amp; return <sup>2</sup>.</p>
        <pre><strong>Input:</strong> [1,2]\nOutput: 3</pre>
        <ul><li>A constraint</li></ul>
        <script>bad()</script><iframe>hidden()</iframe>
        <a href="javascript:bad()">Readable text</a>
        <img src="https://assets.leetcode.com/uploads/example.png" onerror="bad()" style="display:none">
        <img src="javascript:bad()"><img src="https://evil.example/leak.png">
        <img src="https://[bad-ipv6">
    ''')
    elements = [node for node in nodes if isinstance(node, StatementElement)]
    assert [node.tag for node in elements] == ["p", "pre", "ul", "img"]
    assert elements[0].children[1].tag == "code"
    assert elements[1].children[0].tag == "strong"
    assert elements[-1].src == "https://assets.leetcode.com/uploads/example.png"
    serialized = str([node.model_dump() if isinstance(node, StatementElement) else node for node in nodes])
    assert "Readable text" in serialized
    for unsafe in ["bad()", "hidden()", "onclick", "onerror", "javascript:", "evil.example", "style"]:
        assert unsafe not in serialized


def test_plain_text_paste_is_escaped_and_not_interpreted_as_html():
    text = '<script>alert("x")</script>\nInput: [1, 2]'
    nodes = statements.parse_statement(statements.pasted_statement_html(text))
    assert nodes[0].tag == "pre"
    assert nodes[0].children == [text]
