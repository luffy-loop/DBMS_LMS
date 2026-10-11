"""Regression tests for resource access boundaries and upload validation responses."""
import asyncio
import os
from io import BytesIO

os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("RUN_DB_SETUP", "false")
os.environ.setdefault("ENABLE_RESOURCE_VECTOR_SEARCH", "false")

import pytest
from bson import ObjectId
from fastapi import BackgroundTasks, HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from starlette.datastructures import Headers, UploadFile
from starlette.responses import StreamingResponse

import main
from models import User, Course, Enrollment


class FakeResources:
    def __init__(self, document):
        self.document = document
        self.insert_calls = 0

    def find_one(self, *_args, **_kwargs):
        return self.document

    def insert_one(self, *_args, **_kwargs):
        self.insert_calls += 1
        raise AssertionError("invalid or unauthorized uploads must not be stored")


def setup_course_db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    for table in (User.__table__, Course.__table__, Enrollment.__table__):
        table.create(engine)
    session_factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = session_factory()

    owner = User(id=1, name="Course Owner", email="OWNER001", password="x", role="teacher", section="A1")
    another_teacher = User(id=2, name="Other Teacher", email="TEACH002", password="x", role="teacher", section="A1")
    enrolled_student = User(id=3, name="Enrolled Student", email="STUDENT003", password="x", role="student", section="A1")
    outsider_student = User(id=4, name="Outsider Student", email="STUDENT004", password="x", role="student", section="A2")
    db.add_all([owner, another_teacher, enrolled_student, outsider_student])
    db.commit()

    course = Course(id=10, title="Database Systems", description="Relational databases", teacher_id=owner.id)
    db.add(course)
    db.commit()
    db.add(Enrollment(student_id=enrolled_student.id, course_id=course.id))
    db.commit()
    return engine, db, owner, another_teacher, enrolled_student, outsider_student, course


def tear_down_course_db(engine, db):
    db.close()
    for table in (Enrollment.__table__, Course.__table__, User.__table__):
        table.drop(engine)
    engine.dispose()


def test_resource_status_and_download_enforce_course_authorization(monkeypatch):
    engine, db, owner, another_teacher, enrolled, outsider, course = setup_course_db()
    resource_id = ObjectId("64b000000000000000000011")
    fake = FakeResources({
        "_id": resource_id,
        "course_id": course.id,
        "filename": "lesson.txt",
        "content_type": "text/plain",
        "file": b"lesson content",
        "processing_status": "READY",
        "extraction_status": "READY",
        "indexing_status": "LEXICAL_ONLY",
    })
    monkeypatch.setattr(main.mongo_db, "resources", fake)

    try:
        with pytest.raises(HTTPException) as student_error:
            main.resource_status(str(resource_id), {"id": outsider.id, "role": "student"}, db)
        assert student_error.value.status_code == 403

        with pytest.raises(HTTPException) as teacher_error:
            main.download_resource(str(resource_id), {"id": another_teacher.id, "role": "teacher"}, db)
        assert teacher_error.value.status_code == 403

        status = main.resource_status(str(resource_id), {"id": enrolled.id, "role": "student"}, db)
        assert status["status"] == "READY"
        download = main.download_resource(str(resource_id), {"id": enrolled.id, "role": "student"}, db)
        assert isinstance(download, StreamingResponse)
        assert download.status_code == 200
    finally:
        tear_down_course_db(engine, db)


def test_teacher_cannot_upload_to_another_teachers_course(monkeypatch):
    engine, db, owner, another_teacher, _enrolled, _outsider, course = setup_course_db()
    fake = FakeResources(None)
    monkeypatch.setattr(main.mongo_db, "resources", fake)
    upload = UploadFile(
        filename="lesson.txt",
        file=BytesIO(b"course notes"),
        headers=Headers({"content-type": "text/plain"}),
    )
    try:
        with pytest.raises(HTTPException) as error:
            asyncio.run(main.add_resource(
                course.id, BackgroundTasks(), upload, "",
                {"id": another_teacher.id, "role": "teacher"}, db, None,
            ))
        assert error.value.status_code == 404
        assert fake.insert_calls == 0
    finally:
        tear_down_course_db(engine, db)


def test_invalid_course_material_is_returned_as_http_400(monkeypatch):
    engine, db, owner, _another_teacher, _enrolled, _outsider, course = setup_course_db()
    fake = FakeResources(None)
    monkeypatch.setattr(main.mongo_db, "resources", fake)
    upload = UploadFile(
        filename="broken.pdf",
        file=BytesIO(b"not a PDF document"),
        headers=Headers({"content-type": "application/pdf"}),
    )
    try:
        with pytest.raises(HTTPException) as error:
            asyncio.run(main.add_resource(
                course.id, BackgroundTasks(), upload, "",
                {"id": owner.id, "role": "teacher"}, db, None,
            ))
        assert error.value.status_code == 400
        assert "PDF signature" in str(error.value.detail)
        assert fake.insert_calls == 0
    finally:
        tear_down_course_db(engine, db)
