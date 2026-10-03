-- DBMS_LMS CO1 + CO2 upgrade
-- PostgreSQL 14+ / pgvector
-- Run after Lab1_BookFlow.sql and Lab2_BookFlow.sql

CREATE EXTENSION IF NOT EXISTS vector;

-- Stronger relational integrity
ALTER TABLE enrollments
    ADD CONSTRAINT uq_enrollment_student_course
    UNIQUE (student_id, course_id);

ALTER TABLE submissions
    ADD CONSTRAINT uq_submission_assignment_student
    UNIQUE (assignment_id, student_id);

ALTER TABLE assignments
    ADD CONSTRAINT chk_assignment_time
    CHECK (end_time IS NULL OR start_time IS NULL OR end_time > start_time);

ALTER TABLE assignments
    ADD CONSTRAINT chk_assignment_duration
    CHECK (duration_minutes IS NULL OR duration_minutes > 0);

CREATE INDEX IF NOT EXISTS idx_courses_teacher_id
    ON courses(teacher_id);

CREATE INDEX IF NOT EXISTS idx_enrollments_student_id
    ON enrollments(student_id);

CREATE INDEX IF NOT EXISTS idx_enrollments_course_id
    ON enrollments(course_id);

CREATE INDEX IF NOT EXISTS idx_assignments_course_id
    ON assignments(course_id);

CREATE INDEX IF NOT EXISTS idx_submissions_student_id
    ON submissions(student_id);

CREATE INDEX IF NOT EXISTS idx_submissions_assignment_id
    ON submissions(assignment_id);

-- Course progress view
CREATE OR REPLACE VIEW student_course_progress AS
SELECT
    e.student_id,
    e.course_id,
    c.title AS course_title,
    COUNT(a.id) AS total_assessments,
    COUNT(s.id) AS submitted_assessments,
    COUNT(CASE WHEN s.marks IS NOT NULL THEN 1 END) AS graded_assessments,
    COALESCE(ROUND(AVG(s.marks)::numeric, 2), 0) AS average_marks,
    CASE
        WHEN COUNT(a.id) = 0 THEN 0
        ELSE ROUND((COUNT(s.id)::numeric / COUNT(a.id)::numeric) * 100, 2)
    END AS progress_percent
FROM enrollments e
JOIN courses c ON c.id = e.course_id
LEFT JOIN assignments a ON a.course_id = e.course_id
LEFT JOIN submissions s
    ON s.assignment_id = a.id
   AND s.student_id = e.student_id
GROUP BY e.student_id, e.course_id, c.title;

-- Course performance view
CREATE OR REPLACE VIEW course_performance AS
SELECT
    c.id AS course_id,
    c.title AS course_title,
    COUNT(DISTINCT e.student_id) AS enrolled_students,
    COUNT(DISTINCT s.id) AS submissions,
    COALESCE(ROUND(AVG(s.marks)::numeric, 2), 0) AS average_marks,
    COUNT(DISTINCT CASE WHEN s.marks IS NOT NULL THEN s.student_id END) AS graded_students
FROM courses c
LEFT JOIN enrollments e ON e.course_id = c.id
LEFT JOIN assignments a ON a.course_id = c.id
LEFT JOIN submissions s ON s.assignment_id = a.id
GROUP BY c.id, c.title;

-- Assignment submission summary
CREATE OR REPLACE VIEW assignment_submission_summary AS
SELECT
    a.id AS assignment_id,
    a.title,
    a.course_id,
    c.title AS course_title,
    COUNT(e.student_id) AS enrolled_students,
    COUNT(s.id) AS submissions,
    COUNT(CASE WHEN s.marks IS NOT NULL THEN 1 END) AS graded_submissions,
    COALESCE(ROUND(AVG(s.marks)::numeric, 2), 0) AS average_marks
FROM assignments a
JOIN courses c ON c.id = a.course_id
LEFT JOIN enrollments e ON e.course_id = a.course_id
LEFT JOIN submissions s
    ON s.assignment_id = a.id
   AND s.student_id = e.student_id
GROUP BY a.id, a.title, a.course_id, c.title;

-- CTE: students with their current course performance
WITH student_scores AS (
    SELECT
        s.student_id,
        e.course_id,
        AVG(s.marks) AS average_marks
    FROM submissions s
    JOIN assignments a ON a.id = s.assignment_id
    JOIN enrollments e
      ON e.student_id = s.student_id
     AND e.course_id = a.course_id
    WHERE s.marks IS NOT NULL
    GROUP BY s.student_id, e.course_id
)
SELECT
    student_id,
    course_id,
    ROUND(average_marks::numeric, 2) AS average_marks
FROM student_scores
ORDER BY average_marks DESC;

-- Window function: rank students within each course
WITH student_scores AS (
    SELECT
        s.student_id,
        a.course_id,
        AVG(s.marks) AS average_marks
    FROM submissions s
    JOIN assignments a ON a.id = s.assignment_id
    WHERE s.marks IS NOT NULL
    GROUP BY s.student_id, a.course_id
)
SELECT
    student_id,
    course_id,
    ROUND(average_marks::numeric, 2) AS average_marks,
    RANK() OVER (
        PARTITION BY course_id
        ORDER BY average_marks DESC
    ) AS course_rank,
    DENSE_RANK() OVER (
        PARTITION BY course_id
        ORDER BY average_marks DESC
    ) AS dense_course_rank
FROM student_scores;

-- Window function: cumulative submission activity
SELECT
    student_id,
    assignment_id,
    marks,
    ROW_NUMBER() OVER (
        PARTITION BY student_id
        ORDER BY id
    ) AS submission_number,
    AVG(marks) OVER (
        PARTITION BY student_id
        ORDER BY id
        ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
    ) AS running_average
FROM submissions
WHERE marks IS NOT NULL
ORDER BY student_id, id;

-- pgvector storage for course resources
CREATE TABLE IF NOT EXISTS resource_embeddings (
    id BIGSERIAL PRIMARY KEY,
    source_id VARCHAR(255) NOT NULL,
    source_type VARCHAR(50) NOT NULL,
    course_id INTEGER,
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    embedding VECTOR(384) NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_resource_embedding_source UNIQUE (source_id)
);

CREATE INDEX IF NOT EXISTS idx_resource_embeddings_course
    ON resource_embeddings(course_id);

CREATE INDEX IF NOT EXISTS idx_resource_embeddings_vector
    ON resource_embeddings
    USING hnsw (embedding vector_cosine_ops);

-- Example similarity search:
-- SELECT source_id, title, 1 - (embedding <=> '[...]') AS similarity
-- FROM resource_embeddings
-- ORDER BY embedding <=> '[...]'
-- LIMIT 8;
