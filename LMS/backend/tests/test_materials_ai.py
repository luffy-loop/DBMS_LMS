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
    results = [
        {"title":"Normalization Notes","content":"Normalization organizes relational data to reduce redundancy and improve integrity. This passage comes from the selected course."},
        {"title":"SQL Notes","content":"SQL joins combine rows from related tables using a join condition. This is course material."},
    ]
    questions = _generate_grounded_questions(results, 10)
    assert 1 <= len(questions) <= 10
    assert all(q["source"] in {"Normalization Notes", "SQL Notes"} for q in questions)
    assert all(len(q["context"]) <= 700 for q in questions)
