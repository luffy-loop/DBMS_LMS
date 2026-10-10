import os
os.environ["ENVIRONMENT"] = "test"
os.environ["RUN_DB_SETUP"] = "false"

from types import SimpleNamespace

import evaluation_service as es
from evaluation_service import calculate_lexical_answer_score


def test_paraphrased_primary_key_answer_receives_partial_credit():
    reference = "Primary key is unique identification"
    answer = "Primary Key is also the unique and different identification for the database"
    assert calculate_lexical_answer_score(answer, reference) >= 0.70


def test_answer_with_no_matching_concepts_scores_low_and_should_be_reviewed():
    reference = "Primary key is unique identification"
    answer = "Photosynthesis converts sunlight into chemical energy"
    assert calculate_lexical_answer_score(answer, reference) < 0.20


def test_short_answer_synonyms_are_matched():
    assert calculate_lexical_answer_score(
        "A key uniquely identifies each table row",
        "A primary key is a unique identifier"
    ) > 0.20


def test_lexical_score_is_bounded_and_empty_answers_score_zero():
    assert calculate_lexical_answer_score("", "A reference answer with concepts") == 0.0
    assert calculate_lexical_answer_score("Some student answer", "") == 0.0
    score = calculate_lexical_answer_score("A unique identifier key", "A primary key is unique")
    assert 0.0 <= score <= 1.0


def test_rubric_evaluator_grants_partial_credit_for_close_paraphrase(monkeypatch):
    reference = "Primary key is unique identification"
    answer = "The primary key is the unique and different identification of database"
    vector = [1.0] + [0.0] * 383
    criterion = SimpleNamespace(
        id=1,
        criterion_text=reference,
        max_marks=10.0,
        criterion_embedding=vector,
    )
    monkeypatch.setattr(es, "generate_embedding", lambda text: vector)
    monkeypatch.setattr(es, "compute_pgvector_similarity", lambda db, a, b: 0.10)
    monkeypatch.setattr(
        es,
        "classify_nli",
        lambda premise, hypothesis: {"contradiction": 0.0, "entailment": 0.0, "neutral": 1.0},
    )

    marks, similarity, result = es.evaluate_hybrid_descriptive(
        None, answer, 10, reference, vector, [criterion]
    )

    assert 0 < marks <= 10
    assert result["criteria"][0]["awarded_marks"] >= 7
    assert result["criteria"][0]["covered"] is True



def test_concise_correct_answer_matches_sentence_in_detailed_reference():
    reference = (
        "The main purpose of the system clock in an STM32 microcontroller is to provide "
        "a timing signal that synchronizes and controls the operation of the CPU and peripheral devices. "
        "It determines how fast the microcontroller executes instructions and operates its peripherals, "
        "such as timers, UART, SPI, and I2C."
    )
    answer = (
        "The system clock controls the speed of the CPU and synchronizes all operations "
        "in the STM32 microcontroller."
    )
    reference_parts = [
        part.strip()
        for part in __import__("re").split(r"(?<=[.!?])\s+", reference)
        if len(part.split()) >= 3
    ]
    score = max(
        calculate_lexical_answer_score(answer, candidate)
        for candidate in [reference, *reference_parts]
    )
    assert score >= 0.35

def test_embedding_failure_uses_lexical_fallback_and_requires_review(monkeypatch):
    reference = "A primary key uniquely identifies each row in a database table"
    answer = "A unique key identifies each row in the table"
    monkeypatch.setattr(es, "generate_embedding", lambda text: (_ for _ in ()).throw(RuntimeError("model unavailable")))
    monkeypatch.setattr(es, "classify_nli", lambda **kwargs: (_ for _ in ()).throw(AssertionError("NLI should not load after embedding failure")))

    marks, similarity, result = es.evaluate_hybrid_descriptive(
        None, answer, 10, reference, None, []
    )

    assert 0 < marks <= 10
    assert similarity == 0.0
    assert result["embedding_fallback_used"] is True
    assert result["scoring_fallback"] == "lexical_review_required"
    assert result["review_status"] == "review_required"
    assert result["evaluator_confidence"] <= 0.49


def test_empty_and_one_word_answers_require_review_with_no_confidence():
    for answer in ("", "yes"):
        marks, similarity, result = es.evaluate_hybrid_descriptive(
            None, answer, 10, "A detailed reference answer", None, []
        )
        assert marks == 0
        assert result["review_status"] == "review_required"
        assert result["evaluator_confidence"] == 0.0
        assert result["evaluation_state"] == "empty_or_too_short_answer"


def test_zero_vector_similarity_is_not_semantic_evidence():
    assert es.compute_pgvector_similarity(None, [0.0] * 384, [1.0] + [0.0] * 383) == 0.0
    assert es.compute_pgvector_similarity(None, [1.0] + [0.0] * 383, [0.0] * 384) == 0.0


def test_invalid_embedding_dimensions_trigger_reviewable_lexical_fallback(monkeypatch):
    monkeypatch.setattr(es, "generate_embedding", lambda text: [1.0, 2.0])
    marks, similarity, result = es.evaluate_hybrid_descriptive(
        None, "A primary key identifies each row", 10,
        "A primary key uniquely identifies each row in a database table", None, []
    )
    assert result["embedding_fallback_used"] is True
    assert result["review_status"] == "review_required"
    assert result["evaluator_confidence"] <= 0.49
    assert "semantic_embeddings" in result["degraded_capabilities"]


def test_nli_failure_is_reported_as_degraded_and_requires_review(monkeypatch):
    vector = [1.0] + [0.0] * 383
    criterion = SimpleNamespace(
        id=1,
        criterion_text="A primary key uniquely identifies each row",
        max_marks=10.0,
        criterion_embedding=vector,
    )
    monkeypatch.setattr(es, "generate_embedding", lambda text: vector)
    monkeypatch.setattr(es, "compute_pgvector_similarity", lambda db, a, b: 0.8)
    monkeypatch.setattr(
        es,
        "classify_nli",
        lambda **kwargs: {
            "contradiction": 0.0,
            "entailment": 0.0,
            "neutral": 1.0,
            "fallback_error": "model unavailable",
        },
    )
    marks, similarity, result = es.evaluate_hybrid_descriptive(
        None, "A primary key uniquely identifies each row", 10,
        criterion.criterion_text, vector, [criterion]
    )
    assert 0 <= marks <= 10
    assert result["nli_fallback_used"] is True
    assert result["review_status"] == "review_required"
    assert result["evaluator_confidence"] <= 0.49
    assert "natural_language_inference" in result["degraded_capabilities"]


def test_manual_grading_fixture_has_bounded_reviewed_score_ranges():
    import json
    from pathlib import Path
    fixture_path = Path(__file__).parent / "fixtures" / "descriptive_grading_cases.json"
    fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
    assert "do not establish statistical grading accuracy" in fixture["purpose"]
    assert len(fixture["cases"]) >= 4
    for case in fixture["cases"]:
        low, high = case["expected_marks_range"]
        total = sum(item["marks"] for item in case["rubric"])
        assert 0 <= low <= high <= total
        assert case["reference_answer"].strip()
        assert case["student_answer"].strip()


def test_manual_fixture_catches_relevant_irrelevant_and_contradictory_answers():
    import json
    from pathlib import Path
    cases = json.loads(
        (Path(__file__).parent / "fixtures" / "descriptive_grading_cases.json").read_text(encoding="utf-8")
    )["cases"]
    by_id = {case["id"]: case for case in cases}
    correct = by_id["primary-key-paraphrase"]
    irrelevant = by_id["primary-key-irrelevant"]
    contradiction = by_id["primary-key-contradiction"]
    assert calculate_lexical_answer_score(correct["student_answer"], correct["reference_answer"]) >= 0.45
    assert calculate_lexical_answer_score(irrelevant["student_answer"], irrelevant["reference_answer"]) < 0.20
    detected, details, correctness = es.detect_contradictions_and_correctness(
        contradiction["student_answer"], contradiction["reference_answer"], []
    )
    assert detected
    assert details
    assert correctness < 1.0
