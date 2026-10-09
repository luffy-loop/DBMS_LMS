# Distributed Learning Management System (DBMS LMS)
## Complete Project Architecture, Design, and Technical Reference

---

## 1. Project Context & Background

* **Project Title:** Distributed Learning Management System with Scalable Backend Architecture
* **Course:** Database Systems Engineering and Distributed Backend Development
* **Institution:** KLH University
* **Presented By:** 
  * M. Ruchee (2510030087)
  * Oddiraj Sridhruti (2510030016)
  * Poojasri Reddy (2510030093)
* **Supervisor:** Dr. Gayathri Edamadaka
* **GitHub Repository:** [DBMS_LMS](https://github.com/luffy-loop/DBMS_LMS)

---

## 2. Problem Statement & Motivation

Traditional Learning Management Systems (LMS) typically rely on a single monolithic database (often purely relational). When student enrollment spikes, course materials accumulate, and heavy workloads occur concurrently (e.g., timed online assessments, PDF uploads, analytical queries, and document searches), monolithic LMS platforms face severe bottlenecks:
1. **Database Contention:** Mixed transactional operations (submitting tests) and heavy analytical reporting (leaderboards, performance metrics) degrade query performance.
2. **Unstructured File Overhead:** Storing binary files, syllabi, and variable document shapes directly in SQL tables causes bloat and rigid schema migrations.
3. **Keyword-Only Search:** Traditional `LIKE '%query%'` or basic full-text searches fail to understand student intent and semantic meaning across course lecture notes.

### Solution: Polyglot Persistence & AI-Assisted LMS
This project implements a scalable architecture that decouples workloads across specialized storage engines:
* **Relational Storage (PostgreSQL):** For transactional consistency, foreign-key relationships, and analytical reporting views.
* **Document Storage (MongoDB):** For flexible resource schemas, binary PDFs, handouts, and student submission files.
* **Vector Storage (ChromaDB):** For semantic embeddings and AI-assisted search across lecture notes and course materials.
* **FastAPI Backend:** Lightweight asynchronous REST API layer connecting clients to the polyglot persistence engines.
* **React 19 + Vite Frontend:** Modern, responsive, and animated user interface supporting Student, Teacher, and Admin personas.

---

## 3. High-Level Architecture Diagram

```
+-----------------------------------------------------------------------------------+
|                           CLIENT LAYER (React 19 + TypeScript + Vite)              |
|   - Student Portal       - Teacher Dashboard       - Admin Control Console         |
|   - AI Search / Copilot  - Quiz Lab Engine         - Real-time Analytics Views     |
+-----------------------------------------------------------------------------------+
                                         |
                                         | HTTP / REST (JWT in Bearer Header)
                                         v
+-----------------------------------------------------------------------------------+
|                         API GATEWAY & BACKEND (FastAPI / Uvicorn)                 |
|                                                                                   |
|  +--------------------+  +---------------------+  +----------------------------+  |
|  |   Auth & Security  |  |   Core LMS Engine   |  |   Analytics Engine (SQL)   |  |
|  | - JWT verification |  | - Courses & Enrolls |  | - student_course_progress  |  |
|  | - PBKDF2 hashing   |  | - Timed Assessments |  | - course_performance       |  |
|  | - Role permissions |  | - PDF Submission    |  | - Window-function ranks    |  |
|  +--------------------+  +---------------------+  +----------------------------+  |
|                                                                                   |
|  +-----------------------------------------------------------------------------+  |
|  |                               AI & Retrieval Engine                         |  |
|  | - Sentence Transformers (`all-MiniLM-L6-v2`)                                |  |
|  | - ChromaDB Vector Collection (`lms_resources`)                              |  |
|  | - Study Copilot (Contextual RAG Q&A)                                        |  |
|  | - Automatic Quiz & Distractor Generator                                     |  |
|  +-----------------------------------------------------------------------------+  |
+-----------------------------------------------------------------------------------+
                                |                 |                 |
                                v                 v                 v
            +-----------------------+  +--------------------+  +--------------------+
            |      PostgreSQL       |  |      MongoDB       |  |      ChromaDB      |
            | (Relational / ACID)   |  |  (Document / Files)|  |  (Vector Database) |
            +-----------------------+  +--------------------+  +--------------------+
            | - Users & Roles       |  | - Course PDFs      |  | - Resource vectors |
            | - Courses & Enrolls   |  | - Handouts         |  | - 384-dim embeddings|
            | - Assignments / Tests |  | - Submission files |  | - Cosine similarity|
            | - Submissions & Marks |  | - Metadata docs    |  | - Fast top-k hits  |
            | - SQL Analytics Views |  |                    |  |                    |
            +-----------------------+  +--------------------+  +--------------------+
```

---

## 4. Deep-Dive: Polyglot Persistence Layer

### 4.1 PostgreSQL (Relational System-of-Record)
PostgreSQL handles all core transactional data requiring strict ACID guarantees, constraints, and relationships.

#### Primary Tables:
1. `users`: Stores user identity, hashed passwords, roles (`student`, `teacher`, `admin`), and assigned academic section (`A1`–`A7`).
2. `courses`: Course definitions mapped to teacher foreign keys.
3. `enrollments`: Many-to-many relationship mapping students to courses with unique constraint `(student_id, course_id)`.
4. `assignments`: Assessment details, supporting both assignments and timed tests with constraint checks (`end_time > start_time`, `duration_minutes > 0`).
5. `submissions`: Student answers, timestamps, and awarded marks with unique constraint `(assignment_id, student_id)`.

#### Relational Integrity & Indexes (`LMS/database/co1_co2_upgrade.sql`):
* `uq_enrollment_student_course`: Prevents duplicate enrollment.
* `uq_submission_assignment_student`: Prevents double submissions.
* Foreign Key Indexes: B-Tree indexes on `idx_courses_teacher_id`, `idx_enrollments_student_id`, `idx_enrollments_course_id`, `idx_assignments_course_id`, and `idx_submissions_student_id`.

#### Advanced SQL Analytics (Views & Window Functions):
* `student_course_progress` (View): Computes total assessments, completed submissions, graded count, average score, and completion percentage per student per course.
* `course_performance` (View): Aggregates enrolled student counts, total submissions, class-wide average marks, and graded student metrics.
* `assignment_submission_summary` (View): Summarizes turn-in rates per individual assignment.
* **Window Functions implemented in queries:**
  * `RANK() OVER (PARTITION BY course_id ORDER BY average_marks DESC)`: Dense and sparse leaderboard ranking.
  * `ROW_NUMBER() OVER (PARTITION BY student_id ORDER BY id)`: Chronological submission sequencing.
  * `AVG(marks) OVER (PARTITION BY student_id ORDER BY id ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)`: Real-time cumulative running average tracking student trajectory.

### 4.2 MongoDB (Document & File Storage)
MongoDB is used for document-oriented and binary file storage:
* `resources`: Uploaded course notes and handouts. When a teacher uploads a PDF, the backend extracts the textual content for indexing and stores the raw binary data alongside metadata (`filename`, `content_type`, `created_at`, `teacher_id`, `course_id`).
* `submission_files`: Attached student PDF solutions linked to relational `submission_id`.

### 4.3 ChromaDB (Local Vector Store)
* Vector retrieval engine running embedded locally (`./vector_data`).
* Embeddings generated using `sentence-transformers/all-MiniLM-L6-v2` (384-dimensional dense vectors).
* Stores tokenized text representations of course descriptions, PDF contents, and handouts.
* Automatically syncs changes between MongoDB/PostgreSQL and ChromaDB during retrieval queries.
* Provides a robust lexical fallback if embedding generation is temporarily cold.

---

## 5. Artificial Intelligence & Learning Features

### 5.1 Semantic Resource Search (`/ai-search`)
* Rather than simple keyword matching, students search using natural questions (e.g., *"How does B-Tree indexing work?"*).
* Student enrolled courses filter candidate documents so students only retrieve content they have permission to access.
* Returns ranked results with distance metrics and extracted context snippets.

### 5.2 Study Copilot (`/study-copilot`)
* An interactive AI learning assistant built directly into the student portal.
* Leverages Retrieval-Augmented Generation (RAG):
  1. Identifies query intent and checks the internal domain knowledge repository (`study_knowledge.py`).
  2. Queries ChromaDB for semantic matches across lecture notes.
  3. Synthesizes relevant sentence fragments from course documents into concise, source-cited study responses.

### 5.3 Automated Quiz Generator (`/quiz/generate`)
* Automatically generates multi-choice revision quizzes for enrolled courses.
* Extracts key topics from lecture materials and generates dynamic distractors and definitions.
* Allows students to test their understanding before examinations.

### 5.4 Academic Insights Engine
* **Learning Insights (Student):** Detects academic focus areas, overdue assessments, weak performance subjects, and next prioritized learning actions.
* **Teacher Insights:** Provides class distribution histograms, pending grading queues, and course engagement rates.

---

## 6. End-to-End User Roles & Workflows

### 6.1 Student Workflow
1. **Authentication:** Registers using roll number and logs in to receive a signed JWT token.
2. **Course Discovery:** Explores available courses and enrolls in subjects.
3. **Course Learning:** Downloads PDF notes and materials uploaded by the instructor.
4. **Assessment Taking:**
   * Opens active assignments or timed tests.
   * Views countdown timer based on `start_time`, `end_time`, and `duration_minutes`.
   * Submits textual answers and/or attaches solution PDFs.
5. **Grades & Feedback:** Views evaluation marks, teacher comments, and class progress.
6. **AI Study:** Uses Study Copilot, Semantic Search, and AI Quiz Lab.

### 6.2 Teacher Workflow
1. **Course Administration:** Creates new courses with syllabus descriptions.
2. **Material Publishing:** Uploads course PDF notes (automatically parsed and embedded into ChromaDB).
3. **Assessment Authoring:** Creates assignments or timed tests with duration limits and optional PDF problem handouts.
4. **Grading Suite:** Inspects ungraded student submissions, views/downloads submitted PDF answer sheets, and assigns numeric marks.
5. **Analytics & Leaderboard:** Views course performance, turn-in metrics, and student rankings computed via SQL window functions.

### 6.3 Admin Workflow
1. **User Oversight:** Audits registered accounts across students, teachers, and admins.
2. **Section Assignment:** Allocates teachers to specific university sections (`A1` through `A7`).
3. **System Telemetry:** Monitors platform totals (users, courses, submissions, grading loads).

---

## 7. Technology Stack Summary

| Layer | Technologies Used |
| :--- | :--- |
| **Frontend UI** | React 19, TypeScript, Vite, Tailwind CSS v4, Motion (Framer Motion), Lucide React, React Router 7 |
| **Backend API** | Python 3.10+, FastAPI, Uvicorn, Pydantic, Python-Multipart |
| **Relational DB** | PostgreSQL 14+, SQLAlchemy ORM, psycopg2-binary |
| **Document DB** | MongoDB, PyMongo |
| **Vector DB & NLP** | ChromaDB, Sentence-Transformers (`all-MiniLM-L6-v2`), PyPDF |
| **Authentication** | JWT (JSON Web Tokens via python-jose), Passlib (PBKDF2-SHA256 password hashing) |
| **Deployment** | Vercel (Frontend), Uvicorn/Container-ready (Backend) |

---

## 8. Directory & File Breakdown

```
DBMS_LMS/
├── README.md                                             # Main project readme & setup instructions
├── Distributed_Learning_Management_System_...pdf        # Complete technical presentation PDF
├── DBMS LMS1.pptx                                        # Review presentation slide deck
├── Lab1_BookFlow.sql                                     # DDL & constraint validation lab
├── Lab2_BookFlow.sql                                     # Joins, subqueries & aggregations lab
├── Lab3.js                                               # MongoDB document queries lab
├── docs/
│   └── DATABASE_ARCHITECTURE.md                          # Rationale for polyglot persistence design
│
└── LMS/
    ├── database/
    │   └── co1_co2_upgrade.sql                           # PostgreSQL views, indexes, CTEs & window queries
    │
    ├── backend/
    │   ├── main.py                                       # Core API entrypoint & route handlers
    │   ├── models.py                                     # SQLAlchemy ORM database schemas
    │   ├── schemas.py                                    # Pydantic request/response models
    │   ├── database.py                                   # PostgreSQL connection & SessionLocal
    │   ├── mongodb.py                                    # PyMongo connection initialization
    │   ├── auth.py                                       # JWT encoding, decoding & dependency injection
    │   ├── vector_store.py                               # ChromaDB indexer, embeddings & semantic search
    │   ├── analytics.py                                  # SQL view execution & leaderboard routes
    │   ├── learning_insights.py                          # Student progress & recommendation logic
    │   ├── teacher_insights.py                          # Teacher summary statistics
    │   ├── study_copilot.py                              # RAG Q&A study assistant endpoint
    │   ├── study_knowledge.py                            # Built-in DBMS domain knowledge base
    │   ├── quiz_generator.py                             # Automated quiz and distractor generator
    │   └── requirements.txt                              # Python package dependencies
    │
    └── frontend/
        ├── package.json                                  # NPM dependencies & build scripts
        ├── vite.config.ts                                # Vite configuration
        └── src/
            ├── App.tsx                                   # Interactive landing page with architecture diagram
            ├── main.tsx                                  # Client router setup
            ├── config.ts                                 # Backend API URL config
            ├── index.css                                 # Tailwind & design token styles
            ├── components/
            │   └── MobileNav.tsx                         # Mobile navbar
            └── pages/
                ├── Login.tsx / Register.tsx              # Authentication forms
                ├── Dashboard.tsx                         # Student dashboard & course overview
                ├── TeacherDashboard.tsx                  # Teacher control center
                ├── Admin.tsx                             # Admin management & section allocation
                ├── Courses.tsx                           # Course enrollment & catalog
                ├── Assignments.tsx                       # Timed assessments & submission portal
                ├── Marks.tsx                             # Grades & score breakdown
                ├── AISearch.tsx                          # Semantic resource search interface
                ├── StudyCopilot.tsx                      # AI chatbot interface
                ├── QuizLab.tsx                           # Interactive quiz generator & evaluator
                ├── LearningPath.tsx                      # Student progress roadmap
                ├── TeacherInsights.tsx                   # Class performance analytics & leaderboards
                └── Profile.tsx                           # User profile & upcoming deadlines
```

---

## 9. Key API Endpoints Reference

### Authentication
* `POST /register`: Register user with roll number, password, and role.
* `POST /login`: Authenticate and obtain JWT access token.
* `GET /profile`: Fetch authenticated profile, courses, and upcoming deadlines.

### Courses & Enrollments
* `POST /courses`: Create a new course (Teacher only).
* `GET /courses`: List all public courses.
* `POST /enroll`: Enroll in a course (Student only).
* `GET /my-courses`: Fetch enrolled courses for the logged-in student.

### Course Resources & File Streaming
* `POST /courses/{course_id}/resources`: Upload course PDF notes; extracts text into ChromaDB (Teacher only).
* `GET /courses/{course_id}/resources`: List resources for an enrolled course.
* `GET /resources/{resource_id}/download`: Stream resource PDF from MongoDB.

### Assessments & Submissions
* `POST /assignments`: Create timed tests or assignments with optional PDF handout (Teacher only).
* `GET /assignments/{course_id}`: List assignments with status (`open`, `upcoming`, `closed`).
* `POST /submissions`: Submit answer and/or upload PDF solution before deadline (Student only).
* `GET /teacher/submissions`: Fetch pending submissions for teacher's courses.
* `PUT /submissions/{submission_id}/marks`: Grade submission and assign marks (Teacher only).
* `GET /submissions/{submission_id}/download`: Stream student's submitted PDF solution.

### Database Analytics
* `GET /analytics/course-performance`: Query `course_performance` SQL view.
* `GET /analytics/student-progress`: Query `student_course_progress` SQL view for student.
* `GET /analytics/leaderboard/{course_id}`: CTE query ranking students using `RANK() OVER`.

### AI Services
* `GET /ai-search?q={query}`: Vector semantic search across course materials.
* `POST /study-copilot`: Contextual RAG question answering.
* `GET /quiz/generate`: Generates an AI revision quiz based on course concepts.
* `GET /learning-insights`: Personalized student progress analytics.

---

## 10. Local Setup & Execution Instructions

### Backend Setup:
```bash
# 1. Navigate to backend directory
cd LMS/backend

# 2. Create and activate a virtual environment
python3 -m venv venv
source venv/bin/activate   # On Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment variables in a .env file:
# DATABASE_URL=postgresql://user:password@localhost:5432/lms_db
# MONGO_URL=mongodb://localhost:27017
# JWT_SECRET=your_secret_key

# 5. Run the database upgrade scripts in PostgreSQL:
# psql -d lms_db -f ../database/co1_co2_upgrade.sql

# 6. Launch the FastAPI server
uvicorn main:app --reload --port 8000
```

### Frontend Setup:
```bash
# 1. Navigate to frontend directory
cd LMS/frontend

# 2. Install NPM packages
npm install

# 3. Start development server
npm run dev
```

---

## 11. Typical Viva / Presentation Discussion Points

1. **Why Polyglot Persistence instead of doing everything in PostgreSQL?**
   * *Answer:* PostgreSQL provides strong ACID guarantees for student enrollments, marks, and constraints. Storing binary PDF files and unstructured document data in MongoDB keeps the relational tables lean and index-friendly. ChromaDB handles vector embeddings natively without requiring complex external PostgreSQL vector extensions.
2. **How does the AI Search differ from standard database search?**
   * *Answer:* Standard SQL `LIKE` or regex searches look for exact token matches. AI Search generates 384-dimensional dense semantic vector embeddings via `all-MiniLM-L6-v2`. It finds concepts even when different synonyms or phrased questions are used.
3. **How does the system ensure academic integrity on timed tests?**
   * *Answer:* Timed tests enforce both database-level check constraints (`end_time > start_time`) and backend validation (`assessment_deadline()`). Any submission received after the deadline or before the start time is rejected with HTTP 400.
4. **How are real-time analytics kept fast?**
   * *Answer:* Instead of looping and computing metrics in Python, analytics are offloaded directly to PostgreSQL analytical views (`student_course_progress`, `course_performance`) and window functions (`RANK()`, running averages), leveraging relational indexing.
