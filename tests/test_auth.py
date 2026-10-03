"""JWT verification and authenticated HTTP requests against disposable PostgreSQL."""

import csv
import io
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
from auth import TokenVerifier, VerifiedUser
from importing import NOTION_DATA_COLUMNS
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
    assert TokenVerifier(PROJECT).verify(signing(owner)) == VerifiedUser(owner, False)


def test_guest_has_a_verified_individual_identity(signing):
    owner = uuid4()
    assert TokenVerifier(PROJECT).verify(signing(owner, is_anonymous=True)) == VerifiedUser(owner, True)


def test_guest_metadata_cannot_override_signed_anonymous_claim(signing):
    user = TokenVerifier(PROJECT).verify(signing(
        is_anonymous=True, user_metadata={"is_anonymous": False, "problem_limit": None},
    ))
    assert user.is_anonymous is True


@pytest.mark.parametrize("overrides", [
    {"exp": 1}, {"iss": "https://another-project.supabase.co/auth/v1"},
    {"aud": "anon"}, {"role": "service_role"}, {"sub": "not-a-uuid"},
    {"sub": "00000000-0000-0000-0000-000000000000"}, {"is_anonymous": "true"},
    {"is_anonymous": None}, {"is_anonymous": 1},
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


@pytest.mark.parametrize("missing", ["exp", "is_anonymous"])
def test_missing_required_claim_rejected(signing, missing):
    claims = jwt.decode(signing(), options={"verify_signature": False})
    # Use the real signature verifier, but a matching key with a missing claim.
    key = ec.generate_private_key(ec.SECP256R1())
    verifier = TokenVerifier(PROJECT)
    verifier.keys.get_signing_key_from_jwt = lambda token: jwt.PyJWK.from_json(jwt.algorithms.ECAlgorithm.to_jwk(key.public_key()))
    del claims[missing]
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
    ("POST", "/imports/standard/preview", {"csv_text": "anything"}),
    ("POST", "/imports/standard", {"csv_text": "anything"}),
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


@pytest.mark.parametrize("anonymous, other_anonymous", [(False, False), (True, False), (True, True)])
def test_http_ownership_and_same_number_workflow(hosted_client, signing, anonymous, other_anonymous):
    alice_id, bob_id = uuid4(), uuid4()
    alice = {"Authorization": "Bearer " + signing(alice_id, is_anonymous=anonymous)}
    bob = {"Authorization": "Bearer " + signing(bob_id, is_anonymous=other_anonymous)}
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


def capacity_csv(numbers):
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=NOTION_DATA_COLUMNS)
    writer.writeheader()
    writer.writerows({
        "Problem": f"Capacity test #{number}", "Difficulty": "Easy", "Topic": "Arrays",
        "Last Reviewed": "September 10, 2026", "Mastery": "🔵 Mastered",
        "Pattern/Trick": "Keep guest history", "Reviews": "3",
    } for number in numbers)
    return {"csv_text": stream.getvalue()}


def test_standard_import_http_guest_cap_and_ownership(hosted_client, signing):
    guest = {"Authorization": "Bearer " + signing(is_anonymous=True)}
    other = {"Authorization": "Bearer " + signing(is_anonymous=False)}

    def payload(numbers):
        return {"csv_text": "number,name,difficulty,topic\n" + "\n".join(
            f"{number},Unreviewed {number},Easy,Arrays" for number in numbers
        )}

    batch = payload(range(1, 52))
    preview = hosted_client.post("/imports/standard/preview", json=batch, headers=guest)
    assert preview.status_code == 200
    assert len(preview.json()["problems"]) == 51
    assert hosted_client.get("/problems", headers=guest).json() == []
    assert hosted_client.post("/imports/standard", json=batch, headers=guest).status_code == 403
    assert hosted_client.get("/problems", headers=guest).json() == []
    accepted = hosted_client.post("/imports/standard", json=payload(range(1, 51)), headers=guest)
    assert len(accepted.json()["imported_numbers"]) == 50
    assert hosted_client.get("/reviews", headers=guest).json() == []
    assert hosted_client.get("/problems", headers=other).json() == []
    repeated = hosted_client.post("/imports/standard", json=batch, headers=guest)
    assert repeated.status_code == 403
    assert len(hosted_client.get("/problems", headers=guest).json()) == 50
    assert hosted_client.post("/imports/standard", json=payload([1]), headers=guest).json()["skipped_existing_numbers"] == [1]
    assert hosted_client.post("/imports/standard", json=batch, headers=other).status_code == 200
    assert len(hosted_client.get("/problems", headers=other).json()) == 51


def test_guest_http_limit_and_same_owner_upgrade_preserve_collection(hosted_client, signing):
    owner = uuid4()
    guest = {"Authorization": "Bearer " + signing(
        owner, is_anonymous=True, user_metadata={"is_anonymous": False},
    )}
    permanent = {"Authorization": "Bearer " + signing(owner, is_anonymous=False)}
    payload = {"number": 51, "name": "New problem", "difficulty": "Easy", "topic": "Arrays",
               "is_anonymous": False, "problem_limit": None}
    response = hosted_client.post("/imports/notion", json=capacity_csv(range(1, 51)), headers=guest)
    assert response.status_code == 200
    assert len(response.json()["imported_numbers"]) == 50
    assert hosted_client.post("/problems/1/archive", headers=guest).status_code == 200
    assert hosted_client.put("/practice/1/statement", json={"text": "Guest statement"}, headers=guest).status_code == 200
    before = hosted_client.get("/problems", headers=guest).json()
    reviews = hosted_client.get("/reviews", headers=guest).json()
    response = hosted_client.post("/problems", json=payload, headers=guest)
    assert response.status_code == 403
    assert "up to 50 problems" in response.json()["detail"]
    assert "Create an account" in response.json()["detail"]
    assert hosted_client.post("/problems", json={**payload, "number": 1}, headers=guest).status_code == 409
    assert hosted_client.get("/problems", headers=guest).json() == before
    assert hosted_client.get("/reviews", headers=guest).json() == reviews
    # A refreshed, provider-signed permanent identity with the same UUID lifts
    # the cap without moving any data. This simulates conversion, not live mail.
    assert hosted_client.get("/problems", headers=permanent).json() == before
    assert hosted_client.get("/reviews", headers=permanent).json() == reviews
    assert hosted_client.post("/problems", json=payload, headers=permanent).status_code == 201
    assert len(hosted_client.get("/problems", headers=permanent).json()) == 51
    assert len(hosted_client.get("/reviews", headers=permanent).json()) == 50
    assert "Guest statement" in hosted_client.post("/practice/1/statement/load", headers=permanent).text


def test_guest_http_import_rejection_and_delete_free_capacity(hosted_client, signing):
    guest = {"Authorization": "Bearer " + signing(is_anonymous=True)}
    other = {"Authorization": "Bearer " + signing(is_anonymous=True)}
    permanent = {"Authorization": "Bearer " + signing(is_anonymous=False)}
    assert hosted_client.post("/imports/notion", json=capacity_csv(range(1, 50)), headers=guest).status_code == 200
    before = hosted_client.get("/problems", headers=guest).json()
    reviews = hosted_client.get("/reviews", headers=guest).json()
    batch = capacity_csv([1, 50, 51])
    assert hosted_client.post("/imports/notion/preview", json=batch, headers=guest).status_code == 200
    response = hosted_client.post("/imports/notion", json=batch, headers=guest)
    assert response.status_code == 403  # Policy errors must not become import 500s.
    assert "up to 50 problems" in response.json()["detail"]
    assert hosted_client.get("/problems", headers=guest).json() == before
    assert hosted_client.get("/reviews", headers=guest).json() == reviews
    assert hosted_client.post("/imports/notion", json=capacity_csv([1, 50, 50]), headers=guest).json()["imported_numbers"] == [50]
    repeated = hosted_client.post("/imports/notion", json=capacity_csv(range(1, 51)), headers=guest)
    assert repeated.status_code == 200 and repeated.json()["imported_numbers"] == []
    attempt = {"problem_number": 2, "reviewed_on": "2026-10-02", "mastery_level": "Mastered"}
    assert hosted_client.post("/reviews", json=attempt, headers=guest).status_code == 201
    assert hosted_client.post("/imports/notion", json=capacity_csv([1]), headers=other).status_code == 200
    assert len(hosted_client.get("/problems", headers=other).json()) == 1
    assert hosted_client.delete("/problems/1", headers=guest).status_code == 200
    assert hosted_client.post("/imports/notion", json=capacity_csv([51]), headers=guest).status_code == 200
    assert len(hosted_client.get("/problems", headers=guest).json()) == 50
    assert hosted_client.post("/imports/notion", json=capacity_csv(range(1, 61)), headers=permanent).status_code == 200
    assert len(hosted_client.get("/problems", headers=permanent).json()) == 60


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
