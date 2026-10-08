import os
os.environ["ENVIRONMENT"] = "test"
os.environ["RUN_DB_SETUP"] = "false"

import asyncio
import subprocess
import sys
from datetime import datetime, timedelta
from io import BytesIO

from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from fastapi.testclient import TestClient
from jose import jwt
from starlette.datastructures import Headers, UploadFile

from auth import get_user, key, alg
from main import app, read_pdf_upload


def token(role):
    return jwt.encode({"id": 7, "role": role}, key, algorithm=alg)


def test_expired_token_is_rejected():
    creds = HTTPAuthorizationCredentials(
        scheme="Bearer",
        credentials=jwt.encode(
            {"id": 7, "role": "student", "exp": datetime.now() - timedelta(minutes=1)},
            key,
            algorithm=alg,
        ),
    )
    try:
        get_user(creds)
        assert False
    except HTTPException as exc:
        assert exc.status_code == 401


def test_cors_allows_configured_vercel_origin():
    origin = "https://frontend-plum-mu-90.vercel.app"
    with TestClient(app) as client:
        response = client.get("/health", headers={"Origin": origin})
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == origin


def test_cors_does_not_allow_unknown_origin():
    with TestClient(app) as client:
        response = client.get("/health", headers={"Origin": "https://not-the-lms.example"})
    assert response.status_code == 200
    assert "access-control-allow-origin" not in response.headers


def test_oversized_pdf_is_rejected():
    payload = b"x" * (11 * 1024 * 1024)
    upload = UploadFile(
        filename="large.pdf",
        file=BytesIO(payload),
        headers=Headers({"content-type": "application/pdf"}),
    )
    try:
        asyncio.run(read_pdf_upload(upload))
        assert False
    except HTTPException as exc:
        assert exc.status_code == 413


def test_role_boundary_for_admin_endpoint():
    with TestClient(app) as client:
        response = client.get("/admin", headers={"Authorization": f"Bearer {token('student')}"})
    assert response.status_code == 403


def test_notification_admin_endpoint_is_protected():
    with TestClient(app) as client:
        response = client.post(
            "/notifications/system",
            headers={"Authorization": f"Bearer {token('student')}"},
            json={"title": "x", "message": "y"},
        )
    assert response.status_code == 403


def test_production_auth_requires_jwt_secret():
    env = os.environ.copy()
    env["ENVIRONMENT"] = "production"
    env.pop("JWT_SECRET", None)
    result = subprocess.run([sys.executable, "-c", "import auth"], env=env, capture_output=True, text=True)
    assert result.returncode != 0
    assert "JWT_SECRET must be configured in production" in result.stderr
