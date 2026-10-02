"""Fetch public LeetCode descriptions and turn their HTML into safe display nodes."""

from functools import lru_cache
from html import escape
from html.parser import HTMLParser
import re
from urllib.parse import urlsplit

import httpx

from schemas import StatementElement

LEETCODE_BASE = "https://leetcode.com"
HEADERS = {"User-Agent": "LeetCodeReviewTracker/0.1", "Referer": f"{LEETCODE_BASE}/"}
STATEMENT_QUERY = """
    query statement($slug: String!) {
        question(titleSlug: $slug) { questionFrontendId titleSlug content isPaidOnly }
    }
"""
ALLOWED_TAGS = {
    "p", "div", "span", "strong", "b", "em", "i", "u", "pre", "code",
    "ul", "ol", "li", "sup", "sub", "br", "hr", "img", "h2", "h3", "h4",
    "table", "thead", "tbody", "tr", "th", "td", "blockquote",
}
BLOCKED_TAGS = {"script", "style", "iframe", "object", "embed", "svg", "math", "form", "button", "noscript"}
VOID_TAGS = {"br", "hr", "img", "input", "meta", "link", "embed"}
IMAGE_HOSTS = {"assets.leetcode.com", "leetcode.com", "s3-lc-upload.s3.amazonaws.com"}


class StatementUnavailable(Exception):
    def __init__(self, message: str, slug: str | None = None):
        super().__init__(message)
        self.slug = slug


def statement_url(slug: str | None) -> str | None:
    if slug and re.fullmatch(r"[a-z0-9-]+", slug):
        return f"{LEETCODE_BASE}/problems/{slug}/description/"
    return None


def _request_json(path: str, body: dict | None = None) -> dict:
    try:
        with httpx.Client(timeout=12, headers=HEADERS) as client:
            response = (client.get(f"{LEETCODE_BASE}{path}") if body is None
                        else client.post(f"{LEETCODE_BASE}{path}", json=body))
            response.raise_for_status()
            data = response.json()
        if not isinstance(data, dict):
            raise ValueError("Unexpected response")
        return data
    except (httpx.HTTPError, ValueError) as error:
        raise StatementUnavailable("Could not load the statement from LeetCode. Retry, or paste it below.") from error


@lru_cache(maxsize=1)
def _problem_catalog() -> dict[int, tuple[str, bool]]:
    # Fetch only the number-to-page index, not every problem's description.
    data = _request_json("/api/problems/all/")
    entries = data.get("stat_status_pairs")
    if not isinstance(entries, list):
        raise StatementUnavailable("LeetCode's problem index is unavailable. Retry, or paste the statement below.")
    catalog = {}
    for entry in entries:
        if not isinstance(entry, dict) or not isinstance(entry.get("stat"), dict):
            continue
        stat = entry["stat"]
        number, slug = str(stat.get("frontend_question_id", "")), stat.get("question__title_slug")
        if number.isdigit() and isinstance(slug, str) and statement_url(slug):
            catalog[int(number)] = (slug, entry.get("paid_only") is True)
    if not catalog:
        raise StatementUnavailable("LeetCode's problem index is unavailable. Retry, or paste the statement below.")
    return catalog


def fetch_statement(problem_number: int) -> tuple[str, str]:
    entry = _problem_catalog().get(problem_number)
    if entry is None:
        raise StatementUnavailable("This problem number was not found on LeetCode. Reveal details to check it, or paste its statement below.")
    slug, paid = entry
    if paid:
        raise StatementUnavailable("This statement requires LeetCode Premium. You can paste a statement you have access to below.", slug)
    try:
        data = _request_json("/graphql/", {"query": STATEMENT_QUERY, "variables": {"slug": slug}})
    except StatementUnavailable as error:
        raise StatementUnavailable(str(error), slug) from error
    payload = data.get("data")
    question = payload.get("question") if isinstance(payload, dict) else None
    if (not isinstance(question, dict) or str(question.get("questionFrontendId")) != str(problem_number)
            or question.get("titleSlug") != slug):
        raise StatementUnavailable("LeetCode did not return the expected statement. Retry, or paste it below.", slug)
    if question.get("isPaidOnly"):
        raise StatementUnavailable("This statement requires LeetCode Premium. You can paste a statement you have access to below.", slug)
    content = question.get("content")
    if not isinstance(content, str) or not content.strip() or len(content) > 100_000:
        raise StatementUnavailable("This statement is unavailable from LeetCode. Retry, or paste it below.", slug)
    if not parse_statement(content):
        raise StatementUnavailable("LeetCode returned an empty statement. Retry, or paste it below.", slug)
    return content, slug


class _StatementParser(HTMLParser):
    """Keep formatting, but never pass executable HTML or arbitrary attributes."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.nodes: list[StatementElement | str] = []
        self.stack: list[tuple[str, StatementElement | None]] = []
        self.blocked: list[str] = []

    def append(self, node: StatementElement | str) -> None:
        parent = next((element for _, element in reversed(self.stack) if element is not None), None)
        (parent.children if parent is not None else self.nodes).append(node)

    def handle_starttag(self, tag, attrs):
        if self.blocked:
            if tag not in VOID_TAGS:
                self.blocked.append(tag)
            return
        if tag in BLOCKED_TAGS:
            if tag not in VOID_TAGS:
                self.blocked.append(tag)
            return
        if tag not in ALLOWED_TAGS:
            if tag not in VOID_TAGS:
                self.stack.append((tag, None))
            return
        node = StatementElement(tag=tag)
        if tag == "img":
            attributes = dict(attrs)
            source = attributes.get("src") or ""
            try:
                url = urlsplit(source)
            except ValueError:
                return
            if url.scheme != "https" or url.hostname not in IMAGE_HOSTS or url.username or url.password:
                return
            node.src = source
            node.alt = "Problem diagram"
        self.append(node)
        if tag not in VOID_TAGS:
            self.stack.append((tag, node))

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in VOID_TAGS:
            self.handle_endtag(tag)

    def handle_endtag(self, tag):
        if self.blocked:
            if tag in self.blocked:
                del self.blocked[len(self.blocked) - 1 - self.blocked[::-1].index(tag):]
            return
        for index in range(len(self.stack) - 1, -1, -1):
            if self.stack[index][0] == tag:
                del self.stack[index:]
                return

    def handle_data(self, text):
        if not self.blocked:
            self.append(text)


def parse_statement(html: str) -> list[StatementElement | str]:
    parser = _StatementParser()
    parser.feed(html)
    parser.close()
    def has_content(node):
        return bool(node.strip()) if isinstance(node, str) else node.tag == "img" or any(has_content(child) for child in node.children)
    return parser.nodes if any(has_content(node) for node in parser.nodes) else []


def pasted_statement_html(text: str) -> str:
    # Plain text is escaped before caching; preserve pasted examples/line breaks.
    return f"<pre>{escape(text.strip())}</pre>"
