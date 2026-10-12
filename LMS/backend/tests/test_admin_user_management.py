import os
import time
os.environ["ENVIRONMENT"] = "test"
os.environ["RUN_DB_SETUP"] = "false"

from fastapi.testclient import TestClient
from jose import jwt
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from auth import alg, key
from database import get_db
from main import app
from models import User


def setup_db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    User.__table__.create(engine)
    db = TestingSession()
    db.add_all([
        User(id=1, name="Admin", email="ADMIN001", password="hashed", role="admin", section="A1"),
        User(id=2, name="Student", email="STU001", password="hashed", role="student", section="A1"),
    ])
    db.commit()
    def override_db():
        yield db
    app.dependency_overrides[get_db] = override_db
    return engine, db


def token(user_id=1, role="admin"):
    return jwt.encode({"id": user_id, "role": role, "exp": int(time.time()) + 300}, key, algorithm=alg)


def test_admin_can_create_users_and_assign_roles_without_stale_jwt_privileges():
    engine, db = setup_db()
    try:
        with TestClient(app) as client:
            headers = {"Authorization": "Bearer " + token()}
            listed = client.get("/admin/users?page=1&page_size=10", headers=headers)
            assert listed.status_code == 200
            assert listed.json()["total"] == 2
            assigned = client.patch("/admin/users/2/section", headers=headers, json={"section": "A6"})
            assert assigned.status_code == 200
            assert assigned.json()["section"] == "A6"
            assert db.query(User).filter(User.id == 2).one().section == "A6"
            invalid_section = client.patch("/admin/users/2/section", headers=headers, json={"section": "A7"})
            assert invalid_section.status_code == 422
            created = client.post("/admin/users", headers=headers, json={"name": "New Teacher", "roll_no": "TEACH001", "password": "strong-password", "role": "teacher", "section": "A2"})
            assert created.status_code == 201
            teacher_id = created.json()["id"]
            assert created.json()["role"] == "teacher"

            created_admin = client.post(
                "/admin/users",
                headers=headers,
                json={
                    "name": "Second Administrator",
                    "roll_no": "ADMIN002",
                    "password": "another-strong-password",
                    "role": "admin",
                },
            )
            assert created_admin.status_code == 201
            assert created_admin.json()["role"] == "admin"
            admin_account = db.query(User).filter(User.id == created_admin.json()["id"]).one()
            assert admin_account.password != "another-strong-password"
            assert admin_account.role == "admin"
            duplicate = client.post("/admin/users", headers=headers, json={"name": "Duplicate", "roll_no": "TEACH001", "password": "strong-password", "role": "teacher"})
            assert duplicate.status_code == 409
            changed = client.patch("/admin/users/2/role", headers=headers, json={"role": "teacher"})
            assert changed.status_code == 200
            stale = client.get("/admin/users", headers={"Authorization": "Bearer " + token(2, "student")})
            assert stale.status_code == 403
            self_change = client.patch("/admin/users/1/role", headers=headers, json={"role": "student"})
            assert self_change.status_code == 400
            created_user = db.query(User).filter(User.id == teacher_id).first()
            assert created_user.password != "strong-password"
            assert created_user.role == "teacher"
    finally:
        app.dependency_overrides.pop(get_db, None)
        db.close()
        User.__table__.drop(engine)
        engine.dispose()


def test_public_registration_cannot_create_teacher_or_admin():
    engine, db = setup_db()
    try:
        with TestClient(app) as client:
            teacher = client.post("/register", json={"name": "Public Teacher", "roll_no": "PUBLIC001", "password": "strong-password", "role": "teacher"})
            admin = client.post("/register", json={"name": "Public Admin", "roll_no": "PUBLIC002", "password": "strong-password", "role": "admin"})
        assert teacher.status_code == 403
        assert admin.status_code == 403
        assert db.query(User).filter(User.email.in_(["PUBLIC001", "PUBLIC002"])).count() == 0
    finally:
        app.dependency_overrides.pop(get_db, None)
        db.close()
        User.__table__.drop(engine)
        engine.dispose()
