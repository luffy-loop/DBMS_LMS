# LMS Verification Runbook and Evidence

Automated tests use temporary SQLite records and synthetic/in-memory Mongo-like fixtures. They do not create or edit live students, teachers, courses, assignments, submissions, or uploaded files.

## CI coverage

### 1. Material workflow
`LMS/backend/tests/test_verification_workflows.py::test_material_upload_idempotency_processing_listing_download_and_authorization` uses the actual HTTP endpoints and processing function while storing the fixture in memory. It covers upload, processing status, authorized student list/status/download with exact content comparison, Idempotency-Key replay, duplicate rejection, and unauthorized cross-course/owner access.

Expected response statuses:
- Teacher upload: **200**
- Authorized enrolled student list/status/download: **200**
- Same Idempotency-Key replay: **200**, same resource ID
- Duplicate upload without the same request key: **409**
- Unenrolled student or another teacher status/download: **403**

This is an isolated API integration test, not a live browser upload.

### 2. Security matrix
The HTTP test prints one `SECURITY_MATRIX` line per case with expected and actual status and fails when they differ:
- Missing JWT: 401
- Invalid JWT: 401
- Expired JWT: 401
- Student calling `/admin`: 403
- Student calling `/notifications/system`: 403

Existing tests also cover tokens missing expiration, stale role claims, teacher ownership of grading, and one student attempting to download another student's submission.

### 3. Assignment submission to published marks
The isolated API test creates an assignment as the owning teacher, submits work as an enrolled student, grades it with feedback, verifies both marks and feedback remain hidden before publication, publishes the result, and verifies the student sees their own published mark and feedback. The same test checks that a different student cannot see the submission.

Feedback is accepted as an optional `feedback` query parameter on `PUT /submissions/{submission_id}/marks`; existing calls that only provide `marks` remain compatible. Feedback is not shown to students until publication.

### 4. Search quality evaluation
`tests/performance/search_evaluation.py` runs five fixed academic queries against a five-item synthetic corpus with known relevant titles. It reports Hit@1 and mean reciprocal rank, with per-query rankings. The mode is explicitly **lexical keyword matching** and does not claim semantic retrieval. On Render, lexical matching remains the default unless `ENABLE_RESOURCE_VECTOR_SEARCH` is enabled.

These synthetic results are a regression check for the ranking code—not a measure of quality on actual course resources or generated AI answers.

### 5. Performance measurement
CI sends 30 anonymous `GET /health` requests to the live Render backend with concurrency 3. The JSON report records generated time, runtime/platform, target host, HTTP status counts, average/min/max and p50/p95 latency, error rate, requests/second, concurrency and duration. This is a public health endpoint measurement only, not a capacity test or measurement of authenticated workflows.

The login benchmark is run against a temporary SQLite database and synthetic login; it must not be described as production login latency.

CI uploads JUnit, search, and live health JSON reports as a 14-day Actions artifact named `lms-verification-results-<run number>`. Inspect the artifact and run logs before reporting measured outcomes.

## Manual live acceptance still required

Use a dedicated test teacher/student in a non-production test course:
1. Upload one supported TXT/PDF as the teacher and check for `READY`.
2. Confirm an authorized student can list/download the exact upload and find a known term in search.
3. Confirm an unenrolled student cannot view status/download and another teacher cannot view the course material.
4. Create an assignment, submit work as the student, grade it with feedback, publish it, and confirm that the mark and feedback appear only after publishing.
5. Repeat upload with the same idempotency key and confirm no second resource is created.
6. Force a processing failure in a test environment and confirm retry behavior.

**Do not say live upload/download or browser end-to-end verification passed unless these manual steps were actually performed.**


## Durable worker deployment

Quiz jobs are committed to PostgreSQL before the API returns and are processed by the separate `worker.py` process. Material files and processing states are persisted in MongoDB; the worker polls uploaded records and uses atomic leases so multiple workers cannot process the same resource concurrently. Stale quiz jobs are requeued with bounded retry attempts. Docker Compose includes the worker service. In production, deploy `python worker.py` as a separate long-running worker using the same database environment; an API-only Render service does not start it automatically.

## Semantic search evaluation on approved course material

The default CI check is a synthetic lexical regression check, not proof of semantic retrieval quality. Use the opt-in `tests/performance/search_corpus_evaluation.py` harness with a small, approved corpus exported to JSON. It reports lexical ranking and, when the embedding model is available, dense cosine ranking against instructor-labelled relevant titles. Do not include student data, credentials, or confidential materials in the fixture. Keep production vector search disabled on low-memory instances until cold-start, memory and authorization behavior have been measured.
