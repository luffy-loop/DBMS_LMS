# AI Workflows

## Search

The search path is:

query -> cached query embedding -> bounded vector retrieval -> compact context

Only a small top-K set is returned. Course authorization is part of the retrieval filter, so a student's search cannot use another course's private material.

Repeated searches are cached in-process for a short TTL. Cache keys include the authorized course set. A new material index clears the search cache.

Server timing fields include embedding_ms, vector_search_ms, context_build_ms, llm_ms and total_ms.

The Study Copilot is a general study assistant. It can answer supported general academic topics without course selection. A course may be selected as optional authorized context. The current deployment uses the local study-knowledge and retrieval modules rather than an external LLM provider, so llm_ms remains zero.

## Study Copilot

Copilot runs retrieval work outside the FastAPI event loop and has a finite request timeout. The frontend supports idle, searching, completed, failed and cancelled states.

Cancellation stops the browser wait. The backend timeout returns a structured AI_TIMEOUT error.

## Quiz generation

POST /study-copilot accepts a question and optional course_id. No course is required for general study questions. If course_id is supplied, the backend validates enrollment or ownership before retrieval.\n\nPOST /quiz/generate creates a database-backed job and returns a job_id.

Statuses:

- QUEUED
- RETRIEVING
- GENERATING
- COMPLETED
- FAILED
- CANCELLED

The frontend polls the job status and can cancel it. The job state is persisted in PostgreSQL rather than held only in Python memory.

Generated questions are derived from authorized course material. Teacher review/editing is mandatory before assignment publication.

## Quiz -> Assignment

A teacher can edit generated question text/options, add or remove questions, set title/description/start/due/duration, and explicitly publish.

Publication creates one course-level assignment linked to the selected course and creates notifications for active enrolled students. Repeating the publish request after success returns the existing assignment instead of creating another one.

## Timeouts and retries

AI/search operations have bounded timeouts. The frontend never uses an indefinite spinner. Transient failures expose retry actions. Invalid authorization or malformed requests are not retried indefinitely.

The current deployment uses FastAPI background tasks within the modular monolith rather than a separate worker service. The database-backed job state survives browser refreshes; a process restart can interrupt an in-flight background task, which remains a known limitation until a durable worker/queue is introduced.
