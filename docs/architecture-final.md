# Final Architecture

The LMS remains a modular monolith.

## Modules

- FastAPI API layer
- Authentication/RBAC
- PostgreSQL relational data
- MongoDB learning-material storage
- Material extraction/processing module
- Vector retrieval module
- AI job module
- Quiz/assignment module
- Notification module
- Analytics/learning-insights modules
- React/Vite frontend

The modules share one deployment/runtime but have explicit responsibilities and service boundaries. No independent microservices were introduced.

## Reliability boundaries

Uploads, extraction and indexing are separated. AI quiz generation is represented by a PostgreSQL job record. Frontend API calls use a centralized timeout/error/request-ID client.

## Data boundaries

PostgreSQL is authoritative for users, courses, enrollments, assignments, submissions, notifications and AI job state. MongoDB stores learning-material bytes, extracted content and processing metadata. Vector retrieval is filtered by authorized course IDs.

## Known limitation

FastAPI background tasks are still process-local execution. The job state is durable, but the work itself is not resumed automatically after a process restart. A dedicated worker/queue is a future scaling step, not a requirement for the current modular-monolith deployment.
