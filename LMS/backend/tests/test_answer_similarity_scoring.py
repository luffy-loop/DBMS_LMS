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
        for part in __import__("re").split(r"(?<=[.!?])\\s+", reference)
        if len(part.split()) >= 3
    ]
    score = max(
        calculate_lexical_answer_score(answer, candidate)
        for candidate in [reference, *reference_parts]
    )
    assert score >= 0.35
