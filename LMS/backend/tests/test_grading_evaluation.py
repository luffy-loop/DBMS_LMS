import pytest

from tests.performance.grading_evaluation import evaluate


def test_grading_evaluation_reports_error_and_bias_metrics():
    report = evaluate([
        {"predicted_marks": 7, "teacher_marks": 8, "max_marks": 10},
        {"predicted_marks": 4, "teacher_marks": 4, "max_marks": 5},
        {"predicted_marks": 2, "teacher_marks": 3, "max_marks": 5},
    ])
    assert report["sample_count"] == 3
    assert report["mean_absolute_error_marks"] == pytest.approx(2 / 3, abs=1e-4)
    assert report["mean_signed_error_marks"] == pytest.approx(-2 / 3, abs=1e-4)
    assert report["exact_match_rate"] == pytest.approx(1 / 3, abs=1e-4)
    assert report["within_one_mark_rate"] == 1.0


@pytest.mark.parametrize("records", [
    [],
    [{"predicted_marks": 5, "teacher_marks": 5, "max_marks": 0}],
    [{"predicted_marks": 12, "teacher_marks": 5, "max_marks": 10}],
    [{"predicted_marks": float("nan"), "teacher_marks": 5, "max_marks": 10}],
])
def test_grading_evaluation_rejects_invalid_records(records):
    with pytest.raises(ValueError):
        evaluate(records)
