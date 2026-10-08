from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from jose import jwt
import os

os.environ.setdefault("ENVIRONMENT", "test")

from auth import alg, get_user, key
from main import app
from fastapi.testclient import TestClient


def test_missing_token_is_rejected():
    try:
        get_user(None)
        assert False
    except HTTPException as exc:
        assert exc.status_code == 401
        assert exc.detail == "Authorization token required"


def test_invalid_token_is_rejected():
    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials="not-a-valid-token")
    try:
        get_user(creds)
        assert False
    except HTTPException as exc:
        assert exc.status_code == 401
        assert exc.detail == "Invalid token"


def test_valid_token_returns_claims():
    token = jwt.encode({"id": 7, "role": "student"}, key, algorithm=alg)
    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
    assert get_user(creds) == {"id": 7, "role": "student"}


def test_health_is_lightweight():
    with TestClient(app) as client:
        r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}
    assert "X-Request-ID" in r.headers
    assert "X-Process-Time" in r.headers


def test_login_requires_request_body():
    with TestClient(app) as client:
        r = client.post("/login", json={})
    assert r.status_code == 422
    assert r.json()["detail"] == "Request validation failed"


def test_unauthorized_api_returns_http_error():
    with TestClient(app) as client:
        r = client.get("/profile")
    assert r.status_code == 401
    assert r.json()["detail"] == "Authorization token required"
