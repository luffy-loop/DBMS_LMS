import os
os.environ["ENVIRONMENT"] = "test"
os.environ["RUN_DB_SETUP"] = "false"

from datetime import datetime, timedelta, timezone
import inspect
from types import SimpleNamespace

from exam_evaluation import get_now, is_low_score, normalize_datetime
from main import assessment_deadline, submit_assignment
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


def test_evaluation_clock_is_utc_naive_for_database_storage():
    now = get_now()
    assert now.tzinfo is None
    assert abs((datetime.utcnow() - now).total_seconds()) < 5


def test_timezone_aware_assessment_times_normalize_to_utc():
    local_time = datetime(2026, 10, 9, 9, 0, tzinfo=timezone(timedelta(hours=5, minutes=30)))
    assert normalize_datetime(local_time) == datetime(2026, 10, 9, 3, 30)


def test_submission_endpoint_uses_sync_worker_for_cpu_bound_evaluation():
    assert not inspect.iscoroutinefunction(submit_assignment)


def test_question_answer_parser_rejects_malformed_duplicate_and_foreign_ids():
    from main import parse_question_answers
    allowed = {21, 22}
    for raw in ("{", "null", "{\"question_id\":21}"):
        try:
            parse_question_answers(raw, allowed)
            assert False
        except ValueError:
            pass
    for raw, expected in [
        ('[{"question_id":21},{"question_id":21}]', "Duplicate"),
        ('[{"question_id":99}]', "does not belong"),
    ]:
        try:
            parse_question_answers(raw, allowed)
            assert False
        except ValueError as exc:
            assert expected in str(exc)


def test_pdf_mapping_is_single_question_only_and_unreadable_files_need_review():
    from main import map_pdf_answers
    one = [{"id": 21, "question_type": "descriptive"}]
    mapped, status = map_pdf_answers(one, {}, "", "The operating system schedules processes.")
    assert mapped[21]["student_answer"].startswith("The operating system")
    assert status == "mapped"
    many = [{"id": 21, "question_type": "descriptive"}, {"id": 22, "question_type": "descriptive"}]
    try:
        map_pdf_answers(many, {}, "", "The operating system schedules processes.", readable_pdf=True)
        assert False
    except ValueError as exc:
        assert "question-wise" in str(exc).lower()
    mapped, status = map_pdf_answers(many, {}, "", "", readable_pdf=False)
    assert status == "manual_review"
    assert all(item.get("manual_review_required") for item in mapped.values())


def test_ai_suggested_aggregate_is_not_saved_as_final_marks():
    source = open("exam_evaluation.py", encoding="utf-8").read()
    assert "submission.marks = None" in source
    assert "submission.marks = None if failed_evaluation else rounded_marks" not in source



def test_assessment_report_supports_server_side_section_filter_and_csv_export():
    source = open("main.py", encoding="utf-8").read()
    assert 'section: str | None = None' in source
    assert 'enrolled_query.filter(User.section == section)' in source
    assert '"Roll Number", "Student Name"' in source
    assert '"Submission Status", "Marks Obtained", "Maximum Marks", "Grading Status"' in source
    assert 'iter(["\\ufeff" + output.getvalue()])' in source
    assert 'text_value.lstrip()[:1] in {"=", "+", "-", "@"}' in source


def test_admin_marks_overview_is_role_guarded_and_filterable():
    source = open("main.py", encoding="utf-8").read()
    assert '@app.get("/admin/marks-overview")' in source
    assert 'if user["role"] != "admin":' in source
    assert 'course_id: int | None = None' in source
    assert 'assignment_id: int | None = None' in source


def test_login_401_does_not_clear_existing_session_and_logout_is_deduplicated():
    source = open("../frontend/src/api.ts", encoding="utf-8").read()
    assert 'if(path==="/login"||path==="/register"||!token||invalidatedToken===token)return' in source
    assert 'invalidateSessionFor401(path,token)' in source


def test_low_score_review_threshold_uses_unrounded_exact_boundary():
    from exam_evaluation import is_low_score

    for awarded, maximum, expected in [
        (0, 100, True),
        (24, 100, True),
        (24.99, 100, True),
        (25, 100, False),
        (26, 100, False),
        (9, 40, True),
        (10, 40, False),
        (24.999, 100, True),
    ]:
        assert is_low_score(awarded, maximum) is expected


def test_low_score_review_threshold_rejects_invalid_maximum_safely():
    from exam_evaluation import is_low_score

    assert is_low_score(0, 0) is False
    assert is_low_score(0, -1) is False
