import time
from dataclasses import replace

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient

from app.core import auth
from app.main import app

POOL_ID = "eu-west-1_TestPool"
CLIENT_ID = "test-client-id"
ISSUER = f"https://cognito-idp.eu-west-1.amazonaws.com/{POOL_ID}"


@pytest.fixture(scope="module")
def private_key():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


@pytest.fixture(autouse=True)
def configured_auth(monkeypatch, private_key):
    """Real token verification against a locally generated key instead of Cognito's JWKS."""
    monkeypatch.setattr(
        auth,
        "settings",
        replace(
            auth.settings,
            aws_region="eu-west-1",
            cognito_user_pool_id=POOL_ID,
            cognito_client_id=CLIENT_ID,
            auth_disabled=False,
        ),
    )
    monkeypatch.setattr(auth, "_signing_key", lambda token: private_key.public_key())


@pytest.fixture
def http():
    # No dependency overrides here: the real get_current_user runs.
    with TestClient(app) as c:
        yield c


def make_token(private_key, **overrides) -> str:
    claims = {
        "sub": "user-123",
        "iss": ISSUER,
        "client_id": CLIENT_ID,
        "token_use": "access",
        "exp": int(time.time()) + 3600,
    }
    claims.update(overrides)
    claims = {k: v for k, v in claims.items() if v is not None}
    return jwt.encode(claims, private_key, algorithm="RS256", headers={"kid": "test"})


def bearer(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_health_is_public(http):
    assert http.get("/health").status_code == 200


def test_missing_header_is_401(http):
    resp = http.get("/expenses/monthly-summary")
    assert resp.status_code == 401
    assert resp.headers["www-authenticate"] == "Bearer"


def test_garbage_token_is_401(http):
    assert http.get("/expenses/", headers=bearer("not-a-jwt")).status_code == 401


def test_valid_token_is_accepted(http, table, private_key):
    from app.db.dynamodb import get_table

    app.dependency_overrides[get_table] = lambda: table
    try:
        resp = http.get("/expenses/", headers=bearer(make_token(private_key)))
    finally:
        app.dependency_overrides.clear()
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.parametrize(
    "overrides",
    [
        {"exp": int(time.time()) - 10},  # expired
        {"iss": "https://cognito-idp.eu-west-1.amazonaws.com/eu-west-1_Other"},  # other pool
        {"client_id": "someone-elses-client"},  # other app client
        {"token_use": "id"},  # id token, not access token
        {"exp": None},  # no expiry
        {"sub": None},  # no subject
    ],
    ids=["expired", "wrong-issuer", "wrong-client", "id-token", "no-exp", "no-sub"],
)
def test_bad_claims_are_401(http, private_key, overrides):
    token = make_token(private_key, **overrides)
    assert http.get("/expenses/", headers=bearer(token)).status_code == 401


def test_token_signed_by_another_key_is_401(http):
    other_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    assert http.get("/expenses/", headers=bearer(make_token(other_key))).status_code == 401


def test_receipts_endpoints_require_auth(http):
    assert http.post("/receipts/parse").status_code == 401
    assert http.post("/receipts/upload").status_code == 401


def test_get_current_user_returns_sub(private_key):
    from fastapi.security import HTTPAuthorizationCredentials

    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=make_token(private_key))
    assert auth.get_current_user(creds) == "user-123"


def test_auth_disabled_returns_local_user(monkeypatch):
    monkeypatch.setattr(auth, "settings", replace(auth.settings, auth_disabled=True))
    assert auth.get_current_user(None) == auth.LOCAL_USER_ID


def test_missing_cognito_config_fails_closed(monkeypatch):
    monkeypatch.setattr(auth, "settings", replace(auth.settings, cognito_user_pool_id=""))
    with pytest.raises(RuntimeError, match="COGNITO"):
        auth.get_current_user(None)
