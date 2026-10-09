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
from database import get_db
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from models import User



def install_student_db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    User.__table__.create(engine)
    db = TestingSession()
    db.add(User(id=7, name="Test", email="TEST007", password="hashed", role="student", section="A1"))
    db.commit()
    def override_db():
        yield db
    app.dependency_overrides[get_db] = override_db
    return engine, db

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



def test_valid_pdf_is_accepted_even_if_browser_mime_is_generic():
    import asyncio
    from pypdf import PdfWriter
    from io import BytesIO
    from starlette.datastructures import Headers, UploadFile
    stream = BytesIO()
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    writer.write(stream)
    upload = UploadFile(filename="answer.pdf", file=BytesIO(stream.getvalue()), headers=Headers({"content-type": "application/octet-stream"}))
    data, extracted = asyncio.run(read_pdf_upload(upload))
    assert data.startswith(b"%PDF-")
    assert isinstance(extracted, str)

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
    engine, db = install_student_db()
    try:
        with TestClient(app) as client:
            response = client.get("/admin", headers={"Authorization": f"Bearer {token('student')}"})
            stale_admin = client.get("/admin", headers={"Authorization": f"Bearer {token('admin')}"})
        assert response.status_code == 403
        assert stale_admin.status_code == 403
    finally:
        app.dependency_overrides.pop(get_db, None)
        db.close()
        User.__table__.drop(engine)
        engine.dispose()


def test_notification_admin_endpoint_is_protected():
    engine, db = install_student_db()
    try:
        with TestClient(app) as client:
            response = client.post(
                "/notifications/system",
                headers={"Authorization": f"Bearer {token('student')}"},
                json={"title": "x", "message": "y"},
            )
        assert response.status_code == 403
    finally:
        app.dependency_overrides.pop(get_db, None)
        db.close()
        User.__table__.drop(engine)
        engine.dispose()


def test_production_auth_requires_jwt_secret():
    env = os.environ.copy()
    env["ENVIRONMENT"] = "production"
    env.pop("JWT_SECRET", None)
    result = subprocess.run([sys.executable, "-c", "import auth"], env=env, capture_output=True, text=True)
    assert result.returncode != 0
    assert "JWT_SECRET must be configured in production" in result.stderr
