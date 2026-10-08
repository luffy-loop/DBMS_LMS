# DBMS LMS

A full-stack Learning Management System built with React, FastAPI, PostgreSQL, MongoDB, and AI-powered search and study tools.

DBMS LMS brings student, teacher, and admin workflows into one platform while combining relational data, document storage, vector search, and AI-assisted learning features.

## Live Demo

**Frontend:**  
https://frontend-plum-mu-90.vercel.app/

**Backend:**  
https://dbms-lms-hwvp.onrender.com

**Repository:**  
https://github.com/luffy-loop/DBMS_LMS

## What It Does

### Student
- Register and log in with role-based access
- Browse and enroll in courses
- View course resources
- Submit assignments and PDF work
- Take timed assessments
- Track deadlines and submission status
- View marks and academic progress
- Use AI Search and Study Copilot
- Generate AI-assisted quizzes

### Teacher
- Create and manage courses
- Upload course resources and assignment handouts
- Create assignments and timed tests
- View student submissions
- Grade submissions and publish marks
- Track assessment and grading statistics
- View teacher learning insights

### Admin
- Protected admin authentication and role-based access
- Access the admin area for platform-level workflows

## AI Features

The project extends a conventional LMS with AI-assisted learning workflows:

- **AI Search** — semantic search across learning resources
- **Study Copilot** — contextual study assistance
- **Quiz Generator** — AI-assisted quiz creation
- **Learning Insights** — student learning analytics
- **Teacher Insights** — assessment and grading analytics
- **Vector Search** — resource retrieval using embeddings

PDF resources can be processed and stored for retrieval and AI-assisted workflows.

## Architecture

The current implementation is organized as a layered full-stack application:

```
React + TypeScript + Vite
          |
          v
       FastAPI
          |
    +-----+-----+
    |           |
    v           v
PostgreSQL   MongoDB
    |           |
    |           +---- PDF / resource data
    |
    +---- Users
    +---- Courses
    +---- Enrollments
    +---- Assessments
    +---- Submissions
    +---- Marks

          FastAPI AI Modules
                 |
                 v
        Vector Search / Embeddings
```

### Data responsibilities

**PostgreSQL**
- Users and roles
- Courses
- Enrollments
- Assignments and tests
- Submissions
- Marks
- Notifications

**MongoDB**
- Uploaded resources
- PDF/assignment files
- Document-oriented learning content

**Vector layer**
- Embeddings and semantic retrieval for learning resources

## Authentication & Authorization

Authentication uses JWT-based login with password hashing.

Access is controlled by application roles:

```
Student  -> student workflows
Teacher  -> teaching workflows
Admin    -> admin workflows
```

Protected endpoints validate the authenticated user's role before allowing access to role-specific operations.

## Tech Stack

### Frontend
- React 19
- TypeScript
- Vite
- React Router
- Tailwind CSS
- Motion
- Lucide React

### Backend
- Python
- FastAPI
- SQLAlchemy
- Uvicorn
- JWT authentication
- Passlib password hashing

### Databases & AI
- PostgreSQL
- MongoDB
- ChromaDB
- Sentence Transformers
- PyPDF

### Deployment
- Vercel frontend
- Render Python backend

## Project Structure

```
DBMS_LMS/
├── LMS/
│   ├── backend/
│   │   ├── main.py
│   │   ├── models.py
│   │   ├── schemas.py
│   │   ├── database.py
│   │   ├── mongodb.py
│   │   ├── auth.py
│   │   ├── vector_store.py
│   │   ├── learning_insights.py
│   │   ├── study_copilot.py
│   │   ├── quiz_generator.py
│   │   └── teacher_insights.py
│   └── frontend/
│       └── React + TypeScript application
├── Lab*.sql / Lab*.js
├── DBMS LMS1.pptx
├── Distributed_Learning_Management_System_with_Scalable_Backend_Architecture.pdf
└── README.md
```

## Core Workflow

```
Register / Login
      |
      v
Role-based Dashboard
      |
      +--> Student --> Enroll --> Learn --> Submit --> View Marks
      |
      +--> Teacher --> Create Course --> Create Assessment --> Grade
      |
      +--> Admin --> Platform Administration

Learning Resources
      |
      v
PDF Processing
      |
      v
Embeddings / Vector Search
      |
      v
AI Search / Study Copilot / Quiz Generation
```

## Database Design

The system intentionally uses different storage models for different workloads.

**PostgreSQL** handles structured relational data where relationships and transactional consistency matter.

**MongoDB** handles document-oriented resources and uploaded learning content.

**Vector search** supports semantic retrieval over learning resources instead of relying only on keyword matching.

This combination demonstrates polyglot persistence within a single learning platform.

## Current Status

The core LMS workflow is implemented and deployed, including authentication, role-based access, courses, enrollment, resources, assignments, timed tests, submissions, grading, marks, AI search, study assistance, quiz generation, and analytics.

The project uses a modular monolithic backend with explicit service/module boundaries and a migration path toward independently deployable services.

## Known Architecture Gap

The project specification explores distributed and scalable backend architecture. The current repository is **not yet a collection of independently deployed microservices**; the main application currently runs through a FastAPI backend with modular routers and supporting database/AI components.

Future architecture work can split independently scalable responsibilities such as:

```
Frontend
   |
API / Gateway
   |
   +---- Core LMS Service
   +---- AI / Search Service
   +---- Analytics Service
   |
   +---- PostgreSQL
   +---- MongoDB + Vector Store
```

This section is intentionally explicit so the repository reflects the implementation accurately rather than overstating the current architecture.

## Running Locally

### Backend

```bash
cd LMS/backend
pip install -r requirements.txt
uvicorn main:app --reload
```

Configure the required database, MongoDB, JWT, and AI/vector environment variables before starting the backend.

For normal production runs, keep `RUN_DB_SETUP=false`. Schema changes are managed with Alembic. For a fresh local database, `RUN_DB_SETUP=true` runs the non-destructive migration baseline during startup; for an existing database created before Alembic, stamp the baseline once with `alembic stamp 0001_initial` after verifying the schema.

Recommended backend environment variables:

```env
DATABASE_URL=postgresql+psycopg2://...
JWT_SECRET=replace-with-a-long-random-secret
ENVIRONMENT=development
CORS_ORIGINS=http://localhost:5173
RUN_DB_SETUP=false
DB_POOL_SIZE=10
DB_MAX_OVERFLOW=20
DB_POOL_TIMEOUT=10
DB_POOL_RECYCLE=1800
SLOW_REQUEST_MS=150
MAX_UPLOAD_MB=10
```

Production deployments must provide a real `JWT_SECRET`; the development fallback is rejected when `ENVIRONMENT=production`.

For Vercel, configure `VITE_API_URL` in the Production environment to the public HTTPS FastAPI backend URL. The frontend intentionally fails fast during a production build when this variable is missing instead of silently falling back to localhost. The backend `CORS_ORIGINS` must include the exact Vercel production origin (scheme + host, no path).

### Frontend

```bash
cd LMS/frontend
npm install
npm run dev
```

The frontend communicates with the FastAPI backend through the configured API endpoint.

## Notifications

Notifications are stored in PostgreSQL and delivered through internal service functions so they can later be extracted into an independent service. Implemented events include assignment creation, submission receipt, marks publication, course/resource updates, and admin system notifications. Users can list their own notifications and mark them read.

## Performance Evaluation

A repeatable HTTP benchmark is available at `LMS/backend/tests/performance/benchmark.py`. It reports request count, successes, failures, average latency, p50, p95, error rate, requests/second, concurrency, and duration. Example:

```bash
python tests/performance/benchmark.py --base-url https://dbms-lms-hwvp.onrender.com --path /health --requests 100 --concurrency 10
```

Authenticated endpoints can be measured by supplying `--token`. No benchmark numbers are claimed here unless the tool has actually been run against a configured environment.

## Database Migrations

Alembic is included for schema management. `LMS/backend/alembic/versions/0001_initial.py` is a non-destructive baseline that creates missing tables and preserves the existing schema. Existing deployments should be verified and then stamped with `alembic stamp 0001_initial`; future schema changes should be added as incremental revisions. `RUN_DB_SETUP=true` is retained as a compatibility bootstrap for local/reproducible environments.

## Security Evaluation

See `docs/security-evaluation.md` for the implemented security checks and explicit limits on what the project claims.

## What This Project Demonstrates

- Full-stack application development
- Relational database design
- NoSQL document storage
- Vector search and embeddings
- JWT authentication and RBAC
- File and PDF processing
- AI feature integration
- REST API development
- React/TypeScript frontend engineering
- Deployment and production debugging
- Designing toward scalable backend architecture

## Backend Scalability Notes

The backend remains a modular monolith rather than being split into microservices prematurely. Database connections use a configurable SQLAlchemy pool, MongoDB uses a bounded connection pool, authentication password verification is moved off the async event loop, and expensive schema/index initialization is opt-in through `RUN_DB_SETUP`.

`GET /health` is a lightweight liveness check. `GET /health/ready` verifies PostgreSQL and MongoDB connectivity for deployment readiness checks.

Request duration is exposed through the `X-Process-Time` response header, and requests above `SLOW_REQUEST_MS` are logged for investigation.

## Future Work

- Independently deployable backend services
- Event-driven architecture when scale justifies it
- Mobile application
- Further analytics and horizontal scaling

## Author

[Poojasri Reddy](https://github.com/luffy-loop)


## Docker Development

The repository now includes a reproducible backend stack:

```
Docker Compose
├── backend   FastAPI
├── postgres  PostgreSQL + pgvector
└── mongodb   MongoDB
```

From the repository root:

```bash
docker compose up --build
```

The backend connects to the Docker services using `postgres` and `mongodb` service names rather than `localhost`. Docker remains optional for development; Render continues using the Python runtime directly. PostgreSQL remains the source of truth for relational LMS data; MongoDB is used for document-oriented learning resources and uploaded PDF content.

For local Compose development, `RUN_DB_SETUP` defaults to `true` so a fresh database can initialize itself. For a persistent production deployment, prefer an explicit migration process and set `RUN_DB_SETUP=false`.

Do not commit a real `.env`. Use environment variables or copy the example configuration and replace every secret.

## API Testing with Postman

A ready-to-import collection is available at:

```
docs/postman/LMS.postman_collection.json
docs/postman/LMS.postman_environment.json
```

The collection covers authentication, courses, assignments, submissions, resources, notifications, admin, AI/analytics, and health checks. Use `base_url` for local or set it to the documented Render URL; `production_base_url` is provided as a convenience variable. No real credentials are stored. Login stores the returned JWT in the `access_token` environment variable.

## Backend Testing

Run:

```bash
cd LMS/backend
pytest -q
```

The repository also includes a GitHub Actions backend test workflow that compiles the backend and runs the deterministic test suite on backend changes.

## Production Architecture Notes

The backend intentionally remains one deployable modular monolith. The existing FastAPI routers represent functional modules, while PostgreSQL and MongoDB are isolated by workload rather than duplicated.

The architecture is designed to be horizontally scalable because application state is kept in databases and requests do not depend on process-local session state. A load balancer can therefore place multiple backend instances in front of the same PostgreSQL/MongoDB infrastructure.

Redis is intentionally not mandatory today. It can be introduced later for caching, rate limiting, or background-job coordination without changing the core LMS data model.

The current API paths are preserved for frontend compatibility. The deployed frontend production variable `VITE_API_URL` remains `https://dbms-lms-hwvp.onrender.com`. A future versioned API can be introduced as a compatibility layer rather than breaking existing clients.
