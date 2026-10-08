import os
os.environ["ENVIRONMENT"] = "test"
os.environ["RUN_DB_SETUP"] = "false"

from io import BytesIO
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from fastapi.testclient import TestClient
from jose import jwt
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from auth import alg, get_user, key
from main import app, give_marks, download_submission, read_pdf_upload
from models import User, Course, Assignment, Submission


def make_token(user_id=7, role="student", **extra):
    return jwt.encode({"id": user_id, "role": role, **extra}, key, algorithm=alg)


def test_invalid_signature_is_rejected():
    token = jwt.encode({"id": 7, "role": "student"}, "wrong-secret", algorithm=alg)
    try:
        get_user(HTTPAuthorizationCredentials(scheme="Bearer", credentials=token))
        assert False
    except HTTPException as exc:
        assert exc.status_code == 401


def test_malformed_json_is_rejected_without_stack_trace():
    with TestClient(app) as client:
        response = client.post("/login", content="{", headers={"Content-Type": "application/json"})
    assert response.status_code == 422
    assert "Traceback" not in response.text


def test_invalid_notification_pagination_is_rejected():
    with TestClient(app) as client:
        response = client.get("/notifications?page=0", headers={"Authorization": f"Bearer {make_token()}"})
    assert response.status_code == 422
    assert "Traceback" not in response.text


def test_non_pdf_upload_is_rejected():
    from starlette.datastructures import Headers, UploadFile
    upload = UploadFile(filename="note.txt", file=BytesIO(b"not a pdf"), headers=Headers({"content-type": "text/plain"}))
    try:
        import asyncio
        asyncio.run(read_pdf_upload(upload))
        assert False
    except HTTPException as exc:
        assert exc.status_code == 400


def test_malformed_pdf_is_rejected():
    from starlette.datastructures import Headers, UploadFile
    upload = UploadFile(filename="broken.pdf", file=BytesIO(b"%PDF-not-valid"), headers=Headers({"content-type": "application/pdf"}))
    try:
        import asyncio
        asyncio.run(read_pdf_upload(upload))
        assert False
    except HTTPException as exc:
        assert exc.status_code == 400


def test_teacher_cannot_grade_another_teachers_submission():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    for table in (User.__table__, Course.__table__, Assignment.__table__, Submission.__table__):
        table.create(engine)
    Session = sessionmaker(bind=engine)
    db = Session()
    try:
        teacher_one = User(name="Teacher One", email="T1", password="x", role="teacher", section="A1")
        teacher_two = User(name="Teacher Two", email="T2", password="x", role="teacher", section="A1")
        student = User(name="Student", email="S1", password="x", role="student", section="A1")
        db.add_all([teacher_one, teacher_two, student])
        db.commit()
        course = Course(title="Course", description="Course", teacher_id=teacher_one.id)
        db.add(course)
        db.commit()
        assignment = Assignment(title="Assessment", description="Assessment", course_id=course.id, teacher_id=teacher_one.id, type="assignment")
        db.add(assignment)
        db.commit()
        submission = Submission(assignment_id=assignment.id, student_id=student.id, answer="answer")
        db.add(submission)
        db.commit()
        try:
            give_marks(submission.id, 50, {"id": teacher_two.id, "role": "teacher"}, db)
            assert False
        except HTTPException as exc:
            assert exc.status_code == 403
    finally:
        db.close()
        for table in (Submission.__table__, Assignment.__table__, Course.__table__, User.__table__):
            table.drop(engine)
        engine.dispose()


def test_student_cannot_download_another_students_submission():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    for table in (User.__table__, Course.__table__, Assignment.__table__, Submission.__table__):
        table.create(engine)
    Session = sessionmaker(bind=engine)
    db = Session()
    try:
        one = User(name="One", email="ONE", password="x", role="student", section="A1")
        two = User(name="Two", email="TWO", password="x", role="student", section="A1")
        teacher = User(name="Teacher", email="T", password="x", role="teacher", section="A1")
        db.add_all([one, two, teacher])
        db.commit()
        course = Course(title="Course", description="Course", teacher_id=teacher.id)
        db.add(course)
        db.commit()
        assignment = Assignment(title="Assessment", description="Assessment", course_id=course.id, teacher_id=teacher.id, type="assignment")
        db.add(assignment)
        db.commit()
        submission = Submission(assignment_id=assignment.id, student_id=one.id, answer="private")
        db.add(submission)
        db.commit()
        try:
            download_submission(submission.id, {"id": two.id, "role": "student"}, db)
            assert False
        except HTTPException as exc:
            assert exc.status_code == 403
    finally:
        db.close()
        for table in (Submission.__table__, Assignment.__table__, Course.__table__, User.__table__):
            table.drop(engine)
        engine.dispose()
