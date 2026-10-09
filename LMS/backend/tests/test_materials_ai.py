import io

import pytest
from PIL import Image

from material_service import validate_file, extract_content
from quiz_generator import QuizQuestionPublish
from ai_jobs import _generate_grounded_questions


def test_pdf_signature_is_accepted():
    assert validate_file("notes.pdf", "application/pdf", b"%PDF-1.7") == ".pdf"


def test_pdf_wrong_signature_is_rejected():
    with pytest.raises(ValueError):
        validate_file("notes.pdf", "application/pdf", b"not-a-pdf")


def test_invalid_image_is_rejected():
    with pytest.raises(ValueError):
        validate_file("map.png", "image/png", b"not-an-image")


def test_unsupported_extension_is_rejected():
    with pytest.raises(ValueError):
        validate_file("program.exe", "application/octet-stream", b"MZ")


def test_text_extraction_is_bounded():
    text, _ = extract_content(("hello world\n" * 100).encode(), ".txt")
    assert "hello world" in text


def test_quiz_question_requires_correct_answer_in_options():
    with pytest.raises(Exception):
        QuizQuestionPublish(id=1, question="Q", options=["A", "B"], answer="C")


def test_generated_quiz_is_grounded_and_bounded():
    source = {
        "title": "Database Notes",
        "content": (
            "A primary key is a column that uniquely identifies each row in a relational table. "
            "A foreign key is a column that references a key in another table and maintains referential integrity. "
            "Normalization is a process that organizes relational data to reduce redundant values and prevent anomalies. "
            "An index is a data structure that helps locate rows faster for suitable queries in a database."
        ),
    }
    questions = _generate_grounded_questions([source], 10)
    assert 1 <= len(questions) <= 10
    assert all(q["source"] == "Database Notes" for q in questions)
    assert all(q["answer"] in q["options"] for q in questions)
    assert all(len(q["options"]) == 4 for q in questions)
    assert all(len({option.casefold() for option in q["options"]}) == 4 for q in questions)
    assert all(q["answer"].casefold() not in q["question"].casefold() for q in questions)
    assert all(q["answer"].casefold() not in q["context"].casefold() for q in questions)
    assert all(len(q["context"]) <= 700 for q in questions)

def test_general_study_knowledge_works_without_course_material():
    from study_copilot import build_answer
    result = build_answer("What is a primary key?", [])
    assert "uniquely identifies" in result["answer"].lower()
    assert result["mode"] == "general study knowledge"
    assert result["sources"][0]["course_id"] == 0


def test_general_study_topics_work_without_course_context():
    from study_copilot import build_answer
    for question, phrase in [
        ("What is recursion?", "base case"),
        ("Explain pointers in C", "memory address"),
        ("What is PID control?", "proportional"),
        ("Why does binary search require sorted data?", "sorted"),
    ]:
        result = build_answer(question, [])
        assert phrase in result["answer"].lower()
        assert result["sources"][0]["course_id"] == 0


def test_mutex_lock_knowledge_explains_exclusion_and_usage():
    from study_copilot import build_answer
    result = build_answer("Explain mutex locks in operating systems", [])
    answer = result["answer"].lower()
    for phrase in ("critical section", "acquires", "releases", "mutual-exclusion", "race conditions"):
        assert phrase in answer
    assert result["sources"][0]["title"] == "Mutex Lock"


def test_academic_knowledge_topics_route_without_course_material():
    from study_copilot import build_answer
    cases = [
        ("Explain semaphore synchronization", "semaphore"),
        ("What is a deadlock?", "deadlock"),
        ("Explain SQL normalization", "normalization"),
        ("Explain pointers in C programming", "memory address"),
    ]
    for question, expected in cases:
        result = build_answer(question, [])
        assert expected in result["answer"].lower()
        assert result["mode"] == "general study knowledge"


def test_nonacademic_query_is_not_presented_as_academic_answer():
    from study_copilot import build_answer
    result = build_answer("What is the weather tomorrow?", [])
    assert result["mode"] == "unsupported query"
    assert result["sources"] == []
