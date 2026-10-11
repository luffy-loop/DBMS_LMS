"""Instructor-reviewable regression cases for descriptive-answer evaluation.

These tests exercise deterministic evidence and degraded-model behavior. They are
not a claim of statistically validated grading accuracy.
"""
import os
os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("RUN_DB_SETUP", "false")
os.environ.setdefault("ENABLE_RESOURCE_VECTOR_SEARCH", "false")

from types import SimpleNamespace

import evaluation_service as grading


def test_correct_paraphrase_scores_above_irrelevant_answer():
    reference = "TCP is connection-oriented and provides reliable data delivery."
    paraphrase = "TCP establishes a connection and transfers data dependably."
    irrelevant = "Photosynthesis converts sunlight into chemical energy in plants."

    correct_score = grading.calculate_lexical_answer_score(paraphrase, reference)
    irrelevant_score = grading.calculate_lexical_answer_score(irrelevant, reference)

    assert correct_score > irrelevant_score
    assert correct_score > 0


def test_partial_answer_scores_below_full_answer_and_above_irrelevant():
    reference = "A B-tree index organizes database keys to speed up lookup and insertion."
    full = "A B-tree organizes database keys and makes lookup and insertion faster."
    partial = "A B-tree organizes database keys."
    irrelevant = "The weather is sunny and the plants are growing."

    score_full = grading.calculate_lexical_answer_score(full, reference)
    score_partial = grading.calculate_lexical_answer_score(partial, reference)
    score_irrelevant = grading.calculate_lexical_answer_score(irrelevant, reference)

    assert score_full > score_partial > score_irrelevant


def test_explicit_negation_is_flagged_as_contradiction():
    contradiction, details, correctness = grading.detect_contradictions_and_correctness(
        "TCP is not reliable and does not provide dependable delivery.",
        "TCP is reliable and provides dependable delivery.",
        ["reliable delivery"],
    )

    assert contradiction is True
    assert details
    assert correctness < 1.0


def test_valid_contrast_between_udp_and_tcp_is_not_a_contradiction():
    contradiction, _, correctness = grading.detect_contradictions_and_correctness(
        "Unlike UDP which is connectionless, TCP is connection-oriented.",
        "TCP is connection-oriented.",
        ["connection-oriented"],
    )

    assert contradiction is False
    assert correctness == 1.0


def test_embedding_model_outage_forces_degraded_review_not_confident_grade(monkeypatch):
    def unavailable(_text):
        raise RuntimeError("model unavailable in test")

    monkeypatch.setattr(grading, "generate_embedding", unavailable)
    monkeypatch.setattr(grading, "compute_pgvector_similarity", lambda *_args, **_kwargs: 0.0)
    result, similarity, evidence = grading.evaluate_hybrid_descriptive(
        db=object(),
        student_answer="A B-tree index organizes database keys.",
        question_max_marks=10,
        reference_answer="A B-tree index organizes database keys to speed up lookup.",
        reference_embedding=None,
        rubric_criteria=[
            SimpleNamespace(
                id=1,
                criterion_text="Organizes database keys",
                max_marks=5,
                criterion_embedding=None,
            ),
            SimpleNamespace(
                id=2,
                criterion_text="Speeds up lookup",
                max_marks=5,
                criterion_embedding=None,
            ),
        ],
    )

    assert 0 <= result <= 10
    assert similarity == 0.0
    assert evidence["evaluation_state"] == "degraded"
    assert evidence["embedding_fallback_used"] is True
    assert "semantic_embeddings" in evidence["degraded_capabilities"]
    assert evidence["review_status"] == "review_required"
    assert evidence["evaluator_confidence"] <= 0.49
