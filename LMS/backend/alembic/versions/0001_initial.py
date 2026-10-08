from alembic import op
from database import Base
import models

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    Base.metadata.create_all(bind=bind)
    if bind.dialect.name == "postgresql":
        for statement in (
            "ALTER TABLE assignments ADD COLUMN IF NOT EXISTS type VARCHAR DEFAULT 'assignment'",
            "ALTER TABLE assignments ADD COLUMN IF NOT EXISTS start_time TIMESTAMP",
            "ALTER TABLE assignments ADD COLUMN IF NOT EXISTS end_time TIMESTAMP",
            "ALTER TABLE assignments ADD COLUMN IF NOT EXISTS duration_minutes INTEGER",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS section VARCHAR DEFAULT 'Unassigned'",
            "ALTER TABLE student_question_answers ADD COLUMN IF NOT EXISTS evaluator_confidence DOUBLE PRECISION",
            "ALTER TABLE student_question_answers ADD COLUMN IF NOT EXISTS review_status VARCHAR(30) DEFAULT 'auto_finalized'",
            "ALTER TABLE student_question_answers ADD COLUMN IF NOT EXISTS teacher_override_marks DOUBLE PRECISION",
            "ALTER TABLE student_question_answers ADD COLUMN IF NOT EXISTS teacher_review_note TEXT",
            "ALTER TABLE student_question_answers ADD COLUMN IF NOT EXISTS reviewed_at TIMESTAMP",
            "ALTER TABLE student_question_answers ADD COLUMN IF NOT EXISTS reviewed_by INTEGER REFERENCES users(id) ON DELETE SET NULL",
            "CREATE INDEX IF NOT EXISTS ix_courses_teacher_id ON courses(teacher_id)",
            "CREATE INDEX IF NOT EXISTS ix_assignments_course_id ON assignments(course_id)",
            "CREATE INDEX IF NOT EXISTS ix_assignments_teacher_id ON assignments(teacher_id)",
            "CREATE INDEX IF NOT EXISTS ix_submissions_assignment_id ON submissions(assignment_id)",
            "CREATE INDEX IF NOT EXISTS ix_submissions_student_id ON submissions(student_id)",
            "CREATE INDEX IF NOT EXISTS ix_enrollments_student_course ON enrollments(student_id, course_id)",
            "CREATE INDEX IF NOT EXISTS ix_assessment_questions_assignment ON assessment_questions(assignment_id)",
            "CREATE INDEX IF NOT EXISTS ix_assessment_options_question ON assessment_question_options(question_id)",
            "CREATE INDEX IF NOT EXISTS ix_assessment_rubrics_question ON assessment_question_rubrics(question_id)",
            "CREATE INDEX IF NOT EXISTS ix_sqa_submission ON student_question_answers(submission_id)",
            "CREATE INDEX IF NOT EXISTS ix_sqa_student ON student_question_answers(student_id)",
        ):
            op.execute(statement)


def downgrade():
    raise RuntimeError("Downgrade is intentionally disabled to prevent destructive LMS data loss.")
