import os
os.environ["ENVIRONMENT"] = "test"
os.environ["RUN_DB_SETUP"] = "false"

from datetime import datetime
from fastapi.testclient import TestClient
from jose import jwt
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import sessionmaker

from auth import alg, key
from database import get_db
from main import app
from models import Notification, User


def test_notification_isolation_and_mark_read():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    User.__table__.create(engine)
    Notification.__table__.create(engine)
    db = TestingSession()
    db.add_all([
        User(name="One", email="ONE", password="x", role="student", section="A1"),
        User(name="Two", email="TWO", password="x", role="student", section="A1"),
    ])
    db.commit()
    first = db.query(User).filter(User.email == "ONE").first()
    second = db.query(User).filter(User.email == "TWO").first()
    db.add_all([
        Notification(user_id=first.id, notification_type="system", title="Hello", message="For one", created_at=datetime.now()),
        Notification(user_id=second.id, notification_type="system", title="Private", message="For two", created_at=datetime.now()),
    ])
    db.commit()

    def override_db():
        yield db

    app.dependency_overrides[get_db] = override_db
    try:
        token = jwt.encode({"id": first.id, "role": "student"}, key, algorithm=alg)
        headers = {"Authorization": f"Bearer {token}"}
        with TestClient(app) as client:
            listed = client.get("/notifications", headers=headers)
            assert listed.status_code == 200
            assert len(listed.json()["notifications"]) == 1
            notification_id = listed.json()["notifications"][0]["id"]
            read = client.patch(f"/notifications/{notification_id}/read", headers=headers)
            assert read.status_code == 200
            other_id = db.query(Notification).filter(Notification.user_id == second.id).first().id
            forbidden_read = client.patch(f"/notifications/{other_id}/read", headers=headers)
        assert forbidden_read.status_code == 404
    finally:
        app.dependency_overrides.pop(get_db, None)
        db.close()
        Notification.__table__.drop(engine)
        User.__table__.drop(engine)
        engine.dispose()
