# Reliability verification checklist

## Search retrieval evaluation

The repository includes `tests/performance/search_corpus_evaluation.py`. It compares lexical ranking with embedding cosine ranking using a labelled JSON corpus. Create the file outside Git using **teacher-approved material** and queries with expected relevant titles:

```json
{
  "source": "teacher-approved-material-sample",
  "documents": [
    {"id": "dbms-lesson-1", "title": "Database Normalization", "content": "Approved excerpt...", "course_id": 1}
  ],
  "queries": [
    {"query": "Why do update anomalies occur?", "relevant_titles": ["Database Normalization"]}
  ]
}
```

Run:

```bash
cd LMS/backend
python tests/performance/search_corpus_evaluation.py --corpus /path/to/approved-corpus.json --output verification-results/search-corpus-evaluation.json
```

Use enough independent questions and relevant labels to cover actual course topics and paraphrases. Record Hit@1 and MRR for both modes and test course scoping separately. The checked-in five-query evaluation is synthetic regression coverage, not a measured claim about real course materials. Do not include student records or confidential content in the evaluation JSON.

## Grading evaluation

The new `tests/performance/grading_evaluation.py` evaluates numeric AI-suggested marks against teacher-reviewed marks. Export only numeric rows (`predicted_marks`, `teacher_marks`, `max_marks`) after approval, excluding student names, roll numbers, responses, and identifiers:

```bash
cd LMS/backend
python tests/performance/grading_evaluation.py --dataset /path/to/teacher-reviewed-marks.json --output verification-results/grading-evaluation.json
```

Review MAE, RMSE, signed bias, exact match, and within-one-mark rate by assessment type. A small sample is exploratory only; set acceptance thresholds with teachers and expand the sample before making accuracy claims. Keep the current teacher-review-and-publish workflow.

## Real upload checks

With a dedicated test teacher/course and a student enrolled in that course, exercise valid PDF, DOCX, PPTX, TXT, CSV/XLSX and malformed files. Verify persisted metadata, extraction status/content, download, retry after a processing failure, and unauthorized access from an unassigned teacher and unenrolled student. Capture Render peak memory and restart/OOM logs during upload and concurrent search. Automated fakes are regression coverage, not a substitute for this live test.
