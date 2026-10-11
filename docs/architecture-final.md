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

The FastAPI API remains a modular monolith. A separately runnable durable worker process consumes persisted material-processing records from MongoDB and quiz jobs from PostgreSQL. The API and worker are not a set of independently deployed domain microservices; the worker is a separate execution process with a narrow queue-consumer responsibility.

## Reliability boundaries

Uploads are persisted before processing. The worker polls durable MongoDB resource state and PostgreSQL AI-job state, claims quiz work with row locking, uses MongoDB processing leases, and recovers stale quiz jobs with bounded retry counts. The API may still opportunistically dispatch material processing in-process; the separate worker provides restart recovery when deployed. Frontend API calls use a centralized timeout/error/request-ID client.

## Data boundaries

PostgreSQL is authoritative for users, courses, enrollments, assignments, submissions, notifications and AI job state. MongoDB stores learning-material bytes, extracted content and processing metadata. Vector retrieval is filtered by authorized course IDs.

## Known limitation

The durable worker is included in Docker Compose but must also be deployed as a separate long-running production service with the same PostgreSQL and MongoDB configuration. If only the API service is deployed, queued quiz jobs will not be consumed by this worker. This design improves durability but is not a substitute for a broker-backed queue or independently scalable domain microservices.
