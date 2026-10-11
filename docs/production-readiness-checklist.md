# Production Readiness and Regression Checklist

This checklist is intended for release verification. Automated tests and CI are necessary but do not replace a smoke test against the deployed services.

## Material upload and search

1. Sign in as a teacher who owns a course.
2. Upload a small text-based PDF and one supported office document.
3. Confirm the API accepts the upload and returns a resource identifier.
4. Confirm processing progresses from UPLOADED to PROCESSING to READY.
5. Confirm extraction_status is READY. indexing_status may be READY or LEXICAL_ONLY; semantic-index failure must not make successfully extracted content unavailable.
6. Sign in as an enrolled student and search for a distinctive phrase from the uploaded material.
7. Confirm the student can retrieve only materials from enrolled courses.
8. Verify unsupported extensions, MIME mismatches, malformed office archives, oversized files, and duplicate course content are rejected safely.
9. Confirm a genuine extraction failure is visible as FAILED and does not appear in search results.
10. Check Render logs for memory kills, repeated processing errors, and unexpected 5xx responses during upload.

## Authorization and security

- Verify a missing, malformed, expired, or incorrectly signed JWT is rejected.
- Verify students cannot access another student's submissions or resources for a course they are not enrolled in.
- Verify teachers cannot modify another teacher's courses, assignments, submissions, or marks.
- Verify administrative endpoints reject non-admin accounts.
- Verify CORS allows only configured origins and does not reflect arbitrary origins.
- Never log passwords, bearer tokens, uploaded file contents, database URLs, or secrets.
- File checks must validate extension, MIME type, content signature/structure, filename, size, archive expansion limits, and image pixel limits.

## Grading reliability

Use instructor-reviewed reference cases that cover at least:

- Correct concise answers and valid paraphrases.
- Partially correct answers missing one or more rubric concepts.
- Irrelevant answers with superficial keyword overlap.
- Direct contradictions and negated claims.
- Answers that compare two concepts without contradicting the reference.
- Empty, one-word, extremely long, and malformed answers.
- Embedding/NLI model unavailable or returning invalid evidence.

For each case, record the reference answer, rubric, expected mark range, actual marks, contradiction outcome, confidence, degraded capabilities, and whether teacher review was required. Treat the expected ranges as a regression set, not a statistical accuracy claim. Changes to scoring weights or contradiction rules require review of the full set before release. Keep low-confidence and degraded-model results reviewable by a teacher.

## Deployment checks

Run the backend suite from LMS/backend with pytest -q and verify the latest GitHub Actions run is successful. Build the frontend with npm run build from LMS/frontend.

Check GET /health for liveness and GET /health/ready for PostgreSQL and MongoDB readiness. Verify the deployed backend commit/version matches the intended commit, the frontend uses the correct VITE_API_URL, and CORS includes the exact production frontend origin.

Run one complete student/teacher workflow after deployment: create course, upload resource, wait for processing, search the material, create assessment, submit work, review grading, and publish marks. Check response request IDs, X-Process-Time, backend logs, and memory usage. Do not claim production readiness based on a health endpoint or unit tests alone.

## Operational boundary

Resource extraction and vector indexing are separate stages. A semantic-index failure should preserve successfully extracted content for the lexical fallback. Background tasks currently execute in the API process; durable job state does not guarantee that an interrupted task automatically resumes after a process restart. A durable external worker/queue remains future work.
