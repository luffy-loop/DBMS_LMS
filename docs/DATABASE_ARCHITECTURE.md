# DBMS_LMS Database Architecture

## Polyglot persistence

DBMS_LMS uses each database for the type of data it handles well.

### PostgreSQL

System-of-record data:

- users and roles
- courses
- enrollments
- assignments
- submissions
- relational constraints and transactions
- analytical views and SQL reporting
- vector embeddings through pgvector

### MongoDB

Flexible course-resource data:

- uploaded learning resources
- document metadata
- variable resource fields
- activity/resource documents

### pgvector

Semantic retrieval data:

Course or MongoDB resource -> title and content -> Sentence Transformer (all-MiniLM-L6-v2) -> 384-dimensional embedding -> PostgreSQL + pgvector -> cosine similarity search -> Study Copilot / AI Quiz

The vector table is resource_embeddings.

## Relational analytics

The PostgreSQL upgrade adds:

- student_course_progress view
- course_performance view
- assignment_submission_summary view
- CTE-based student score analysis
- RANK() and DENSE_RANK() course leaderboards
- ROW_NUMBER() submission sequencing
- running averages using window frames

The SQL implementation is in LMS/database/co1_co2_upgrade.sql.

## API analytics

FastAPI exposes the database analytics through:

- GET /analytics/course-performance
- GET /analytics/student-progress
- GET /analytics/leaderboard/{course_id}

These endpoints read from PostgreSQL views and CTE/window-function queries rather than duplicating analytics logic in application code.

## Why this design

PostgreSQL remains authoritative for entities that require relationships, constraints and transactions. MongoDB is used where document shape can vary. pgvector keeps semantic retrieval close to the relational system so course access rules and vector search can be combined in one backend.
