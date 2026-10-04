-- DBMS_LMS Automatic Exam Evaluation Schema
-- PostgreSQL 14+ with pgvector extension

CREATE EXTENSION IF NOT EXISTS vector;

-- 1. Assessment Questions Table (Supports MCQ and Descriptive)
CREATE TABLE IF NOT EXISTS assessment_questions (
    id SERIAL PRIMARY KEY,
    assignment_id INT NOT NULL REFERENCES assignments(id) ON DELETE CASCADE,
    question_text TEXT NOT NULL,
    question_type VARCHAR(20) NOT NULL CHECK (question_type IN ('mcq', 'descriptive')),
    max_marks INT NOT NULL DEFAULT 10 CHECK (max_marks > 0),
    order_index INT NOT NULL DEFAULT 0,
    
    -- MCQ: Pointer to correct option in assessment_question_options
    correct_option_id INT,
    
    -- Descriptive: Teacher reference answer & reusable 384-dimensional vector embedding
    reference_answer TEXT,
    reference_embedding vector(384)
);

CREATE INDEX IF NOT EXISTS idx_assessment_questions_assignment_id
    ON assessment_questions(assignment_id);

-- 2. Assessment Question Options Table (For MCQ questions)
CREATE TABLE IF NOT EXISTS assessment_question_options (
    id SERIAL PRIMARY KEY,
    question_id INT NOT NULL REFERENCES assessment_questions(id) ON DELETE CASCADE,
    option_text TEXT NOT NULL,
    order_index INT NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_assessment_question_options_question_id
    ON assessment_question_options(question_id);

-- 3. Student Question Answers & Evaluation Records
CREATE TABLE IF NOT EXISTS student_question_answers (
    id SERIAL PRIMARY KEY,
    submission_id INT NOT NULL REFERENCES submissions(id) ON DELETE CASCADE,
    question_id INT NOT NULL REFERENCES assessment_questions(id) ON DELETE CASCADE,
    student_id INT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    question_type VARCHAR(20) NOT NULL CHECK (question_type IN ('mcq', 'descriptive')),
    
    -- MCQ fields (No pgvector used for MCQ)
    selected_option_id INT REFERENCES assessment_question_options(id) ON DELETE SET NULL,
    is_correct BOOLEAN,
    
    -- Descriptive fields (Using pgvector)
    student_answer TEXT,
    reference_answer TEXT,
    student_embedding vector(384),
    similarity_score FLOAT,
    
    -- Evaluation metrics
    awarded_marks FLOAT NOT NULL DEFAULT 0.0 CHECK (awarded_marks >= 0.0),
    max_marks INT NOT NULL DEFAULT 10 CHECK (max_marks > 0),
    evaluation_status VARCHAR(30) NOT NULL DEFAULT 'evaluated',
    evaluated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    
    CONSTRAINT uq_submission_question UNIQUE (submission_id, question_id)
);

CREATE INDEX IF NOT EXISTS idx_student_question_answers_submission_id
    ON student_question_answers(submission_id);

CREATE INDEX IF NOT EXISTS idx_student_question_answers_question_id
    ON student_question_answers(question_id);

CREATE INDEX IF NOT EXISTS idx_student_question_answers_student_id
    ON student_question_answers(student_id);
