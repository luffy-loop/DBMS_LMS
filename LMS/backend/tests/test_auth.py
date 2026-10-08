import os
os.environ["ENVIRONMENT"] = "test"
os.environ["RUN_DB_SETUP"] = "false"

from datetime import datetime, timedelta
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from fastapi.testclient import TestClient
from jose import jwt
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import sessionmaker

from auth import alg, get_user, key
from database import get_db
from main import app, pwd
from models import User


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


def test_expired_token_is_rejected():
    token = jwt.encode(
        {"id": 7, "role": "student", "exp": datetime.now() - timedelta(minutes=1)},
        key,
        algorithm=alg,
    )
    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
    try:
        get_user(creds)
        assert False
    except HTTPException as exc:
        assert exc.status_code == 401


def test_valid_token_returns_claims():
    token = jwt.encode({"id": 7, "role": "student"}, key, algorithm=alg)
    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
    assert get_user(creds) == {"id": 7, "role": "student"}


def test_health_is_lightweight():
    with TestClient(app) as client:
        response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert "X-Request-ID" in response.headers
    assert "X-Process-Time" in response.headers


def test_login_requires_request_body():
    with TestClient(app) as client:
        response = client.post("/login", json={})
    assert response.status_code == 422
    assert response.json()["detail"] == "Request validation failed"


def test_login_success_and_failure():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    User.__table__.create(engine)
    db = TestingSession()
    db.add(User(name="Test", email="TEST001", password=pwd.hash("correct"), role="student", section="A1"))
    db.commit()

    def override_db():
        yield db

    app.dependency_overrides[get_db] = override_db
    try:
        with TestClient(app) as client:
            success = client.post("/login", json={"roll_no": "TEST001", "password": "correct"})
            failure = client.post("/login", json={"roll_no": "TEST001", "password": "wrong"})
        assert success.status_code == 200
        assert success.json()["role"] == "student"
        assert success.json()["token"]
        assert failure.status_code == 401
        assert failure.json()["detail"] == "Invalid roll number or password"
    finally:
        app.dependency_overrides.pop(get_db, None)
        db.close()
        User.__table__.drop(engine)
        engine.dispose()


def test_role_boundaries():
    def make_token(role):
        return jwt.encode({"id": 7, "role": role}, key, algorithm=alg)

    with TestClient(app) as client:
        assert client.get("/teacher", headers={"Authorization": f"Bearer {make_token('student')}"}).status_code == 403
        assert client.get("/admin", headers={"Authorization": f"Bearer {make_token('teacher')}"}).status_code == 403
        assert client.get("/student", headers={"Authorization": f"Bearer {make_token('admin')}"}).status_code == 403


def test_unauthorized_api_returns_http_error():
    with TestClient(app) as client:
        response = client.get("/profile")
    assert response.status_code == 401
    assert response.json()["detail"] == "Authorization token required"
