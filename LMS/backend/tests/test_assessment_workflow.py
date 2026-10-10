import os
os.environ["ENVIRONMENT"] = "test"
os.environ["RUN_DB_SETUP"] = "false"

from datetime import datetime, timedelta
from types import SimpleNamespace

from exam_evaluation import is_low_score
from main import assessment_deadline
from models import Submission


def test_low_score_threshold_is_strictly_below_25_percent():
    assert is_low_score(24.99, 100)
    assert not is_low_score(25, 100)
    assert not is_low_score(30, 100)
    assert not is_low_score(0, 0)


def test_ordinary_assignment_uses_due_date_not_exam_duration():
    start = datetime(2026, 10, 9, 10, 0)
    due = start + timedelta(days=2)
    assignment = SimpleNamespace(type="assignment", start_time=start, end_time=due, duration_minutes=30)
    assert assessment_deadline(assignment) == due
    exam = SimpleNamespace(type="exam", start_time=start, end_time=due, duration_minutes=30)
    assert assessment_deadline(exam) == start + timedelta(minutes=30)


def test_new_marks_are_unpublished_and_original_answer_is_preserved():
    submission = Submission(assignment_id=1, student_id=7, answer="student's original answer", marks=2, marks_published=False)
    assert Submission.__table__.c.marks_published.default.arg is False
    assert submission.answer == "student's original answer"
