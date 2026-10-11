"""Compare AI-suggested marks with teacher marks from a numeric-only labelled dataset.

Dataset JSON schema:
[
  {"predicted_marks": 7.5, "teacher_marks": 8, "max_marks": 10},
  {"predicted_marks": 3, "teacher_marks": 4, "max_marks": 5}
]

Do not include names, roll numbers, answers, or other student-identifying data.
This tool evaluates saved suggestions; it does not generate or publish marks.
"""
import argparse
import json
import math
from pathlib import Path


def evaluate(records):
    if not isinstance(records, list) or not records:
        raise ValueError("Dataset must be a non-empty JSON array")

    errors = []
    exact = []
    within_one = []
    within_ten_percent = []
    for index, row in enumerate(records):
        try:
            predicted = float(row["predicted_marks"])
            teacher = float(row["teacher_marks"])
            maximum = float(row["max_marks"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"Record {index + 1} is missing valid numeric marks") from exc
        if not all(math.isfinite(value) for value in (predicted, teacher, maximum)):
            raise ValueError(f"Record {index + 1} contains a non-finite value")
        if maximum <= 0:
            raise ValueError(f"Record {index + 1} must have max_marks > 0")
        if not (0 <= predicted <= maximum and 0 <= teacher <= maximum):
            raise ValueError(f"Record {index + 1} marks must be between 0 and max_marks")

        error = predicted - teacher
        absolute_error = abs(error)
        errors.append(error)
        exact.append(absolute_error < 1e-9)
        within_one.append(absolute_error <= 1.0)
        within_ten_percent.append(absolute_error <= maximum * 0.10)

    count = len(errors)
    mae = sum(abs(error) for error in errors) / count
    rmse = math.sqrt(sum(error * error for error in errors) / count)
    return {
        "sample_count": count,
        "mean_absolute_error_marks": round(mae, 4),
        "root_mean_squared_error_marks": round(rmse, 4),
        "mean_signed_error_marks": round(sum(errors) / count, 4),
        "exact_match_rate": round(sum(exact) / count, 4),
        "within_one_mark_rate": round(sum(within_one) / count, 4),
        "within_ten_percent_of_max_rate": round(sum(within_ten_percent) / count, 4),
        "interpretation": {
            "positive_mean_signed_error": "AI suggestions tend to be higher than teacher marks",
            "negative_mean_signed_error": "AI suggestions tend to be lower than teacher marks",
            "limitations": [
                "Metrics describe only the supplied teacher-reviewed sample.",
                "They do not establish grading fairness or accuracy outside that sample.",
                "AI-suggested marks still require the LMS's existing teacher review workflow."
            ]
        }
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", required=True, help="Path to numeric-only teacher-labelled JSON")
    parser.add_argument("--output", default="", help="Optional JSON report output path")
    args = parser.parse_args()
    records = json.loads(Path(args.dataset).read_text(encoding="utf-8"))
    report = evaluate(records)
    rendered = json.dumps(report, indent=2, sort_keys=True)
    print(rendered)
    if args.output:
        destination = Path(args.output)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(rendered + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
