import os
os.environ["ENVIRONMENT"] = "test"
os.environ["RUN_DB_SETUP"] = "false"

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
