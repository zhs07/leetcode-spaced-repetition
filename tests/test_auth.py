"""JWT verification and authenticated HTTP requests against disposable PostgreSQL."""

import json
import time
from uuid import uuid4

from cryptography.hazmat.primitives.asymmetric import ec
from fastapi import HTTPException
from fastapi.testclient import TestClient
import jwt
from psycopg.conninfo import make_conninfo
import pytest

import main
from auth import TokenVerifier
from postgres_storage import open_pool
from settings import Settings


PROJECT = "https://tracker-test.supabase.co"


@pytest.fixture
def signing(monkeypatch):
    private = ec.generate_private_key(ec.SECP256R1())
    public = json.loads(jwt.algorithms.ECAlgorithm.to_jwk(private.public_key()))
    public.update(kid="test-key", alg="ES256", use="sig")
    monkeypatch.setattr(jwt.PyJWKClient, "fetch_data", lambda self: {"keys": [public]})

    def token(owner=None, **overrides):
        claims = {
            "sub": str(owner or uuid4()), "iss": PROJECT + "/auth/v1",
            "aud": "authenticated", "role": "authenticated",
            "iat": int(time.time()) - 1, "exp": int(time.time()) + 600,
            "is_anonymous": False,
        }
        claims.update(overrides)
        return jwt.encode(claims, private, algorithm="ES256", headers={"kid": "test-key"})
    return token


def test_verified_subject_is_identity(signing):
    owner = uuid4()
    assert TokenVerifier(PROJECT).verify(signing(owner)) == owner


@pytest.mark.parametrize("overrides", [
    {"exp": 1}, {"iss": "https://another-project.supabase.co/auth/v1"},
    {"aud": "anon"}, {"role": "service_role"}, {"sub": "not-a-uuid"},
    {"sub": "00000000-0000-0000-0000-000000000000"}, {"is_anonymous": True},
    {"iat": 9999999999}, {"nbf": 9999999999}, {"exp": None},
])
def test_invalid_claims_rejected(signing, overrides):
    with pytest.raises(HTTPException) as result:
        TokenVerifier(PROJECT).verify(signing(**overrides))
    assert result.value.status_code == 401


def test_forged_signature_unknown_key_and_unsigned_token_rejected(signing):
    valid = signing()
    claims = jwt.decode(valid, options={"verify_signature": False})
    other_key = ec.generate_private_key(ec.SECP256R1())
    for token in [
        jwt.encode(claims, other_key, algorithm="ES256", headers={"kid": "test-key"}),
        jwt.encode(claims, other_key, algorithm="ES256", headers={"kid": "unknown"}),
        jwt.encode(claims, "", algorithm="none"),
        jwt.encode(claims, "a" * 32, algorithm="HS256", headers={"kid": "test-key"}),
        "not-a-token", "x" * 16385,
    ]:
        with pytest.raises(HTTPException) as result:
            TokenVerifier(PROJECT).verify(token)
        assert result.value.status_code == 401


def test_missing_required_claim_rejected(signing):
    claims = jwt.decode(signing(), options={"verify_signature": False})
    # Use the real signature verifier, but a new matching key with a missing exp.
    key = ec.generate_private_key(ec.SECP256R1())
    verifier = TokenVerifier(PROJECT)
    verifier.keys.get_signing_key_from_jwt = lambda token: jwt.PyJWK.from_json(jwt.algorithms.ECAlgorithm.to_jwk(key.public_key()))
    del claims["exp"]
    with pytest.raises(HTTPException) as result:
        verifier.verify(jwt.encode(claims, key, algorithm="ES256", headers={"kid": "test-key"}))
    assert result.value.status_code == 401


def test_key_service_failure_is_retryable(signing, monkeypatch):
    verifier = TokenVerifier(PROJECT)
    def unavailable(token):
        raise jwt.PyJWKClientConnectionError("test outage")
    monkeypatch.setattr(verifier.keys, "get_signing_key_from_jwt", unavailable)
    with pytest.raises(HTTPException) as result:
        verifier.verify(signing())
    assert result.value.status_code == 503


@pytest.fixture
def hosted_client(database, signing, monkeypatch):
    monkeypatch.setattr(main, "open_pool", lambda url: open_pool(
        make_conninfo(database, user="tracker_test_runtime"), sslmode="disable",
    ))
    monkeypatch.setattr(main, "initialize_database", lambda path: pytest.fail("Hosted mode must not touch SQLite"))
    monkeypatch.setattr(main, "fetch_statement", lambda number: ("<p>Public example</p>", "example"))
    app = main.create_app(Settings(
        mode="hosted", database_url="postgresql://test@localhost/test",
        supabase_url=PROJECT, allowed_origins=("http://127.0.0.1:5173",),
    ))
    with TestClient(app) as client:
        yield client


ROUTES = [
    ("GET", "/problems", None), ("GET", "/reviews", None),
    ("GET", "/problems/due", None), ("GET", "/problems/summary", None),
    ("GET", "/problems/1/summary", None), ("DELETE", "/problems/1", None),
    ("POST", "/problems/1/archive", None), ("POST", "/problems/1/restore", None),
    ("POST", "/practice/random", None), ("POST", "/practice/1/statement/load", None),
    ("PUT", "/practice/1/statement", {"text": "Private"}),
    ("POST", "/imports/notion/preview", {"csv_text": "anything"}),
    ("POST", "/imports/notion", {"csv_text": "anything"}),
    ("POST", "/problems", {"number": 1, "name": "Example", "difficulty": "Easy", "topic": "Arrays"}),
    ("POST", "/reviews", {"problem_number": 1, "reviewed_on": "2026-10-01", "mastery_level": "Mastered"}),
]


def test_every_tracker_route_requires_valid_auth(hosted_client, signing):
    for method, path, body in ROUTES:
        for header in [None, "Basic ignored", "Bearer invalid", "Bearer " + signing(exp=1)]:
            headers = {"Authorization": header} if header else {}
            response = hosted_client.request(method, path, json=body, headers=headers)
            assert response.status_code == 401, (method, path, response.text)
    assert hosted_client.get("/health").json() == {"status": "ok"}


def test_http_ownership_and_same_number_workflow(hosted_client, signing):
    alice_id, bob_id = uuid4(), uuid4()
    alice = {"Authorization": "Bearer " + signing(alice_id)}
    bob = {"Authorization": "Bearer " + signing(bob_id)}
    payload = {"number": 1, "name": "Example", "difficulty": "Easy", "topic": "Arrays", "notes": "Bob note", "user_id": str(alice_id)}
    assert hosted_client.post("/problems", json=payload, headers=bob).status_code == 201
    # Body owner is ignored: the token, not request JSON, controls ownership.
    assert hosted_client.get("/problems", headers=alice).json() == []
    for method, path, body in ROUTES:
        if path.startswith("/problems/1") or path.startswith("/practice/1") or path == "/reviews" and method == "POST":
            assert hosted_client.request(method, path, json=body, headers=alice).status_code == 404
    assert hosted_client.post("/problems", json={**payload, "notes": "Alice note"}, headers=alice).status_code == 201
    assert hosted_client.post("/problems", json=payload, headers=alice).status_code == 409
    assert hosted_client.put("/practice/1/statement", json={"text": "Alice paste"}, headers=alice).status_code == 200
    assert hosted_client.put("/practice/1/statement", json={"text": "Bob paste"}, headers=bob).status_code == 200
    attempt = {"problem_number": 1, "reviewed_on": "2020-01-01", "mastery_level": "Mastered"}
    assert hosted_client.post("/reviews", json=attempt, headers=alice).status_code == 201
    assert hosted_client.get("/reviews", headers=bob).json() == []
    assert "Alice paste" in hosted_client.post("/practice/random", headers=alice).text
    assert hosted_client.post("/practice/random", headers=bob).status_code == 404
    assert hosted_client.post("/problems/1/archive", headers=alice).status_code == 200
    assert not hosted_client.get("/problems/1/summary", headers=bob).json()["archived"]
    assert hosted_client.post("/problems/1/restore", headers=alice).status_code == 200
    assert hosted_client.delete("/problems/1", headers=alice).status_code == 200
    assert hosted_client.get("/problems/1/summary", headers=bob).json()["notes"] == "Bob note"
    assert "Bob paste" in hosted_client.post("/practice/1/statement/load", headers=bob).text


def test_cors_allows_only_configured_origin(hosted_client):
    headers = {"Origin": "http://127.0.0.1:5173", "Access-Control-Request-Method": "POST", "Access-Control-Request-Headers": "authorization,content-type"}
    response = hosted_client.options("/problems", headers=headers)
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == headers["Origin"]
    response = hosted_client.options("/problems", headers={**headers, "Origin": "https://untrusted.example"})
    assert response.status_code == 400
    assert "access-control-allow-origin" not in response.headers


@pytest.mark.parametrize("overrides", [
    {"database_url": ""}, {"supabase_url": ""}, {"supabase_url": "http://project.example"},
    {"allowed_origins": ()}, {"allowed_origins": ("*",)}, {"mode": "typo"},
])
def test_hosted_settings_fail_closed(overrides):
    values = dict(mode="hosted", database_url="postgresql://localhost/test", supabase_url=PROJECT, allowed_origins=("https://tracker.example",))
    with pytest.raises(ValueError):
        Settings(**{**values, **overrides})


def test_render_cannot_start_in_local_mode(monkeypatch):
    monkeypatch.setenv("RENDER", "true")
    monkeypatch.setenv("TRACKER_MODE", "local")
    with pytest.raises(ValueError):
        Settings.from_env()
