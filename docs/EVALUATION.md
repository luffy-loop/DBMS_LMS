# LMS Final Evaluation

## Functional testing
Implemented workflows include authentication, RBAC, courses, enrollment, assessments, submissions, grading, marks, PDF resources, notifications, AI search, analytics, study assistance, quiz generation, health/readiness endpoints, and migrations. Automated tests cover authentication, role boundaries, notification isolation, upload validation, CORS, and production secret requirements.

## Authentication and authorization
JWT validation rejects missing, malformed, expired, and invalid-signature tokens. Ownership checks cover teacher-owned courses/assessments, student-owned submissions, enrolled-course resources, and notification isolation.

## Security
Controlled exception handlers avoid returning application stack traces. Secrets are supplied through environment variables. No penetration test, certification, or third-party security audit is claimed.

## Database and scalability
PostgreSQL remains the authoritative relational store. Existing ownership/query indexes are retained where justified. The backend is a modular monolith with explicit functional module boundaries and a migration path toward independently deployable services; it is not represented as independently deployed microservices.

## Performance
LMS/backend/tests/performance/benchmark.py is a repeatable HTTP benchmark reporting average, min/max, p50, p95, error rate, throughput, concurrency, and duration. Safe scenarios include /, /health, and /courses.

Actual live performance values are not recorded because the validation environment could not reach the deployed Render service. Status: **Not measured — outbound access to the deployed Render service was unavailable.**

## Deployment
Backend: https://dbms-lms-hwvp.onrender.com
Frontend: https://frontend-plum-mu-90.vercel.app/
Frontend API variable: https://dbms-lms-hwvp.onrender.com

Live root, health, readiness, and CORS verification: **Not executed — outbound access to the deployed Render service was unavailable.**

## Docker
The repository contains Docker configuration for FastAPI, PostgreSQL/pgvector, MongoDB, persistent volumes, networking, and health checks. Runtime execution: **Not executed — Docker runtime was not used during this validation.**

## Postman
The checked-in collection covers authentication, profile, courses, assignments, submissions, marks, resources, notifications, AI/analytics, admin, and health/readiness. No credentials or JWTs are committed. Postman runtime execution: **Not executed — Postman runtime was unavailable.**

## CI
GitHub Actions is configured to install backend dependencies, set PYTHONPATH, run backend tests, compile the backend, build the frontend, and run accessibility/lint checks. A fresh CI result for this final commit is not claimed until GitHub reports it.

## Accessibility
Primary authentication forms use semantic labels and icon-only controls reviewed in this pass have accessible names. Oxlint JSX accessibility rules are enabled as a static guardrail. This is not accessibility certification; browser/screen-reader testing remains manual.

## Usability
See docs/usability-evaluation.md. **Requires real participants.** No participant-derived results were fabricated.

## Migration
Alembic contains a non-destructive baseline. Existing deployments must be verified and stamped before future revisions are applied. Destructive downgrade is intentionally disabled.

## Limitations and future work
Live deployment checks, live performance numbers, Docker runtime execution, Postman runtime execution, and participant usability results were not available in this validation environment. Large-scale load testing and independently deployed microservices remain future work.
