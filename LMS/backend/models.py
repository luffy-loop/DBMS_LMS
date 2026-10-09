from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, Boolean, ForeignKey, DateTime, UniqueConstraint, CheckConstraint, Index
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
    teacher_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

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
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=False, index=True)
    teacher_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
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
    assignment_id = Column(Integer, ForeignKey("assignments.id"), nullable=False, index=True)
    student_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    answer = Column(String, nullable=False)
    marks = Column(Integer, nullable=True)
    created_at = Column(DateTime, nullable=True, default=datetime.utcnow)
    __table_args__ = (UniqueConstraint("assignment_id", "student_id", name="uq_submission_assignment_student"),)

class AssessmentQuestion(Base):
    __tablename__ = "assessment_questions"
    id = Column(Integer, primary_key=True, index=True)
    assignment_id = Column(Integer, ForeignKey("assignments.id", ondelete="CASCADE"), nullable=False, index=True)
    question_text = Column(String, nullable=False)
    question_type = Column(String(20), nullable=False)  # 'mcq' or 'descriptive'
    max_marks = Column(Integer, nullable=False, default=10)
    order_index = Column(Integer, default=0)
    correct_option_id = Column(Integer, nullable=True)  # References assessment_question_options.id
    reference_answer = Column(String, nullable=True)
    reference_embedding = Column(Vector(384), nullable=True)
    __table_args__ = (
        CheckConstraint("max_marks > 0", name="chk_question_max_marks"),
        CheckConstraint("question_type IN ('mcq', 'descriptive')", name="chk_question_type"),
    )

class AssessmentQuestionOption(Base):
    __tablename__ = "assessment_question_options"
    id = Column(Integer, primary_key=True, index=True)
    question_id = Column(Integer, ForeignKey("assessment_questions.id", ondelete="CASCADE"), nullable=False, index=True)
    option_text = Column(String, nullable=False)
    order_index = Column(Integer, default=0)

class AssessmentQuestionRubric(Base):
    __tablename__ = "assessment_question_rubrics"
    id = Column(Integer, primary_key=True, index=True)
    question_id = Column(Integer, ForeignKey("assessment_questions.id", ondelete="CASCADE"), nullable=False, index=True)
    criterion_text = Column(String, nullable=False)
    max_marks = Column(Float, nullable=False, default=1.0)
    order_index = Column(Integer, default=0)
    criterion_embedding = Column(Vector(384), nullable=True)
    __table_args__ = (
        CheckConstraint("max_marks > 0", name="chk_rubric_max_marks"),
    )

class StudentQuestionAnswer(Base):
    __tablename__ = "student_question_answers"
    id = Column(Integer, primary_key=True, index=True)
    submission_id = Column(Integer, ForeignKey("submissions.id", ondelete="CASCADE"), nullable=False, index=True)
    question_id = Column(Integer, ForeignKey("assessment_questions.id", ondelete="CASCADE"), nullable=False, index=True)
    student_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    question_type = Column(String(20), nullable=False)
    selected_option_id = Column(Integer, ForeignKey("assessment_question_options.id", ondelete="SET NULL"), nullable=True)
    is_correct = Column(Boolean, nullable=True)
    student_answer = Column(String, nullable=True)
    reference_answer = Column(String, nullable=True)
    student_embedding = Column(Vector(384), nullable=True)
    similarity_score = Column(Float, nullable=True)
    awarded_marks = Column(Float, nullable=False, default=0.0)
    max_marks = Column(Integer, nullable=False, default=10)
    evaluation_status = Column(String(30), nullable=False, default="evaluated")
    evaluated_at = Column(DateTime, nullable=False)
    evaluator_version = Column(String(50), nullable=True, default="hybrid-v2-nli")
    evaluator_confidence = Column(Float, nullable=True)
    review_status = Column(String(30), nullable=False, default="auto_finalized")
    teacher_override_marks = Column(Float, nullable=True)
    teacher_review_note = Column(String, nullable=True)
    reviewed_at = Column(DateTime, nullable=True)
    reviewed_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    rubric_evaluation = Column(String, nullable=True)
    __table_args__ = (
        UniqueConstraint("submission_id", "question_id", name="uq_submission_question"),
    )



class Notification(Base):
    __tablename__ = "notifications"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    notification_type = Column(String(40), nullable=False)
    title = Column(String(200), nullable=False)
    message = Column(String(1000), nullable=False)
    read_at = Column(DateTime, nullable=True, index=True)
    created_at = Column(DateTime, nullable=False)
    entity_type = Column(String(40), nullable=True)
    entity_id = Column(String(100), nullable=True)
    __table_args__ = (
        Index("ix_notifications_user_read_created", "user_id", "read_at", "created_at"),
        Index("ix_notifications_user_entity", "user_id", "entity_type", "entity_id"),
    )


class AIJob(Base):
    __tablename__ = "ai_jobs"
    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(String(36), unique=True, nullable=False, index=True)
    job_type = Column(String(40), nullable=False, index=True)
    status = Column(String(30), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    course_id = Column(Integer, ForeignKey("courses.id", ondelete="CASCADE"), nullable=True, index=True)
    payload = Column(String, nullable=False, default="{}")
    result = Column(String, nullable=True)
    error = Column(String, nullable=True)
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)
    assignment_id = Column(Integer, ForeignKey("assignments.id", ondelete="SET NULL"), nullable=True, index=True)


class AuditLog(Base):
    __tablename__ = "audit_logs"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    action = Column(String(80), nullable=False, index=True)
    entity_type = Column(String(40), nullable=True, index=True)
    entity_id = Column(String(100), nullable=True)
    details = Column(String(2000), nullable=True)
    created_at = Column(DateTime, nullable=False, index=True)
    __table_args__ = (Index("ix_audit_logs_created_action", "created_at", "action"), Index("ix_audit_logs_user_created", "user_id", "created_at"))
