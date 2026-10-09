# LMS Security Evaluation

This document records the security checks implemented in the repository. It is an evaluation checklist, not a penetration-test or certification report.

## Automated checks

- Missing JWT: protected endpoints return HTTP 401.
- Malformed JWT: token validation returns HTTP 401.
- Expired JWT: token validation returns HTTP 401.
- Role boundaries: student, teacher, and admin tokens cannot cross protected role endpoints.
- CORS: configured Vercel origins are allowed; an unrelated origin is not granted an allow-origin response.
- Upload validation: non-PDF uploads are rejected and PDFs above MAX_UPLOAD_MB return HTTP 413.
- Error handling: validation, database, and unexpected errors return controlled API responses without stack traces in the response body.
- Logging review: passwords, JWTs, database URLs, and secret values are not intentionally logged.

## Authorization review

The important ownership paths are enforced in the API:

- Students can only access enrolled course resources and their own submissions.
- Teachers can only manage their own courses and assessments.
- Teachers can only grade submissions belonging to their assessments.
- Admin endpoints require the admin role.
- Vector search is scoped to enrolled student courses or teacher-owned courses.

## Operational checks

- JWT_SECRET, DATABASE_URL, and MONGO_URL are required in production.
- CORS is explicit rather than wildcard.
- Upload size is bounded.
- Database connections use bounded pools and timeouts.
- Health and readiness endpoints are unauthenticated.
- Sensitive credentials are supplied through environment configuration.

## Not claimed

This repository does not claim penetration testing, formal threat modeling, security certification, or a third-party security audit.
