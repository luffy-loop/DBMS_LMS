# DBMS LMS

A full-stack Learning Management System built with React, FastAPI, PostgreSQL, MongoDB, and AI-powered search and study tools.

DBMS LMS brings student, teacher, and admin workflows into one platform while combining relational data, document storage, vector search, and AI-assisted learning features.

## Live Demo

**Frontend:**  
https://frontend-5fcio5bcj-poojasrikandhula-6164s-projects.vercel.app/

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
- Vercel

## Project Structure

```
DBMS_LMS/
├── LMS/
│   ├── frontend/
│   │   └── React + TypeScript application
│   └── backend/
│       ├── main.py
│       ├── models.py
│       ├── schemas.py
│       ├── database.py
│       ├── mongodb.py
│       ├── auth.py
│       ├── vector_store.py
│       ├── learning_insights.py
│       ├── study_copilot.py
│       ├── quiz_generator.py
│       └── teacher_insights.py
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

The project is still being extended toward a more independently deployable distributed backend architecture.

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

### Frontend

```bash
cd LMS/frontend
npm install
npm run dev
```

The frontend communicates with the FastAPI backend through the configured API endpoint.

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

## Future Work

- Independently deployable backend services
- Docker-based local development and deployment
- Notification service
- More complete admin management
- Automated backend and frontend CI
- Expanded observability and analytics

## Author

[Poojasri Reddy](https://github.com/luffy-loop)
