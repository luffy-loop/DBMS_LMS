from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, UniqueConstraint, CheckConstraint, Text
from pgvector.sqlalchemy import Vector
from database import Base

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, nullable=False, index=True)
    password = Column(String, nullable=False)
    role = Column(String, nullable=False)
    section = Column(String, nullable=False, default="Unassigned")

class Course(Base):
    __tablename__ = "courses"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    description = Column(String, nullable=False)
    teacher_id = Column(Integer, ForeignKey("users.id"), nullable=False)

class Enrollment(Base):
    __tablename__ = "enrollments"
    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=False, index=True)
    __table_args__ = (UniqueConstraint("student_id", "course_id", name="uq_enrollment_student_course"),)

class Assignment(Base):
    __tablename__ = "assignments"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    description = Column(String, nullable=False)
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=False)
    teacher_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    type = Column(String, nullable=False, default="assignment")
    start_time = Column(DateTime, nullable=True)
    end_time = Column(DateTime, nullable=True)
    duration_minutes = Column(Integer, nullable=True)
    __table_args__ = (
        CheckConstraint("end_time IS NULL OR start_time IS NULL OR end_time > start_time", name="chk_assignment_time"),
        CheckConstraint("duration_minutes IS NULL OR duration_minutes > 0", name="chk_assignment_duration"),
    )

class Submission(Base):
    __tablename__ = "submissions"
    id = Column(Integer, primary_key=True, index=True)
    assignment_id = Column(Integer, ForeignKey("assignments.id"), nullable=False)
    student_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    answer = Column(String, nullable=False)
    marks = Column(Integer, nullable=True)
    __table_args__ = (UniqueConstraint("assignment_id", "student_id", name="uq_submission_assignment_student"),)

class ResourceEmbedding(Base):
    __tablename__ = "resource_embeddings"
    id = Column(Integer, primary_key=True)
    source_id = Column(String(255), nullable=False, unique=True, index=True)
    source_type = Column(String(50), nullable=False)
    course_id = Column(Integer, nullable=True, index=True)
    title = Column(Text, nullable=False)
    content = Column(Text, nullable=False)
    embedding = Column(Vector(384), nullable=False)
