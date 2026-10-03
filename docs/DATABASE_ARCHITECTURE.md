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

### MongoDB

Flexible course-resource data:

- uploaded learning resources
- document metadata
- variable resource fields
- activity/resource documents

### Local semantic search

The LMS keeps semantic resource retrieval separate from the relational database. Course and MongoDB resources are converted into embeddings with the Sentence Transformer model `all-MiniLM-L6-v2` and stored in a local ChromaDB collection.

This keeps PostgreSQL focused on transactional and analytical DBMS responsibilities while ChromaDB handles vector retrieval.

## Relational analytics

The PostgreSQL upgrade adds:

- `student_course_progress` view
- `course_performance` view
- `assignment_submission_summary` view
- CTE-based student score analysis
- `RANK()` and `DENSE_RANK()` course leaderboards
- `ROW_NUMBER()` submission sequencing
- running averages using window frames

The SQL implementation is in `LMS/database/co1_co2_upgrade.sql`.

## API analytics

FastAPI exposes the database analytics through:

- `GET /analytics/course-performance`
- `GET /analytics/student-progress`
- `GET /analytics/leaderboard/{course_id}`

These endpoints read from PostgreSQL views and CTE/window-function queries rather than duplicating analytics logic in application code.

## Why this design

PostgreSQL remains authoritative for entities that require relationships, constraints and transactions. MongoDB is used where document shape can vary. ChromaDB is used for semantic retrieval without adding a PostgreSQL extension dependency.
