import json
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text

from database import get_db, SessionLocal
from models import (
    User, Course, Enrollment, Assignment, Submission,
    AssessmentQuestion, AssessmentQuestionOption, AssessmentQuestionRubric,
    StudentQuestionAnswer
)
from schemas import (
    QuestionCreate, QuestionUpdate, ExamSubmissionCreate,
    RubricCriterionCreate, RubricSuggestionRequest,
    TeacherReviewRequest, QuestionReviewItem
)
from auth import get_user
import evaluation_service as es

router = APIRouter(prefix="", tags=["exam_evaluation"])


def _assessment_deadline(assignment: Assignment):
    deadlines = []
    if assignment.end_time:
        deadlines.append(assignment.end_time)
    if assignment.start_time and assignment.duration_minutes:
        deadlines.append(assignment.start_time + timedelta(minutes=assignment.duration_minutes))
    return min(deadlines) if deadlines else None


def _check_teacher_owns_assignment(assignment_id: int, teacher_id: int, db: Session) -> tuple[Assignment, Course]:
    assignment = db.query(Assignment).filter(Assignment.id == assignment_id).first()
    if not assignment:
        raise HTTPException(status_code=404, detail="Assessment not found")
    course = db.query(Course).filter(Course.id == assignment.course_id).first()
    if not course or course.teacher_id != teacher_id:
        raise HTTPException(status_code=403, detail="You can only manage questions for your own courses")
    return assignment, course


# =========================================================================
# 1. TEACHER: CREATE EXAM QUESTION (MCQ or Descriptive)
# =========================================================================
@router.post("/assignments/{assignment_id}/questions")
def create_question(assignment_id: int, data: QuestionCreate, user=Depends(get_user), db: Session = Depends(get_db)):
    if user["role"] not in ["teacher", "admin"]:
        raise HTTPException(status_code=403, detail="Teacher or admin access only")
    
    if user["role"] == "teacher":
        assignment, _ = _check_teacher_owns_assignment(assignment_id, user["id"], db)
    else:
        assignment = db.query(Assignment).filter(Assignment.id == assignment_id).first()
        if not assignment:
            raise HTTPException(status_code=404, detail="Assessment not found")

    q_type = data.question_type.strip().lower()
    if q_type not in ["mcq", "descriptive"]:
        raise HTTPException(status_code=400, detail="Question type must be 'mcq' or 'descriptive'")

    if data.max_marks <= 0:
        raise HTTPException(status_code=400, detail="Maximum marks must be greater than zero")

    question = AssessmentQuestion(
        assignment_id=assignment.id,
        question_text=data.question_text.strip(),
        question_type=q_type,
        max_marks=data.max_marks,
        order_index=data.order_index,
    )

    if q_type == "mcq":
        if not data.options or len(data.options) < 2:
            raise HTTPException(status_code=400, detail="MCQ must have at least 2 options")
        
        correct_count = sum(1 for opt in data.options if opt.is_correct)
        if correct_count != 1:
            raise HTTPException(status_code=400, detail="MCQ must have exactly one correct option")

        db.add(question)
        db.flush()

        correct_opt_id = None
        for idx, opt in enumerate(data.options):
            option_row = AssessmentQuestionOption(
                question_id=question.id,
                option_text=opt.option_text.strip(),
                order_index=opt.order_index or idx
            )
            db.add(option_row)
            db.flush()
            if opt.is_correct:
                correct_opt_id = option_row.id

        question.correct_option_id = correct_opt_id
        db.commit()
        db.refresh(question)

    else:  # descriptive
        ref_ans = (data.reference_answer or "").strip()
        if not ref_ans or len(ref_ans.split()) < 2:
            raise HTTPException(status_code=400, detail="Descriptive question requires a detailed reference answer")

        # Validate rubric criteria if provided
        if data.rubric_criteria:
            crit_sum = sum(c.max_marks for c in data.rubric_criteria)
            if abs(crit_sum - float(data.max_marks)) > 1e-4:
                raise HTTPException(
                    status_code=400,
                    detail=f"Rubric criteria marks total ({crit_sum}) must equal question maximum marks ({data.max_marks})"
                )
            for c in data.rubric_criteria:
                if c.max_marks <= 0:
                    raise HTTPException(status_code=400, detail="Each rubric criterion must have max_marks > 0")
                if not c.criterion_text or not c.criterion_text.strip():
                    raise HTTPException(status_code=400, detail="Rubric criterion text cannot be empty")

        # Generate 384-dimensional vector embedding for reference answer
        ref_vec = es.generate_embedding(ref_ans)
        question.reference_answer = ref_ans
        question.reference_embedding = ref_vec

        db.add(question)
        db.flush()

        if data.rubric_criteria:
            for idx, c in enumerate(data.rubric_criteria):
                crit_vec = es.generate_embedding(c.criterion_text.strip())
                rubric_row = AssessmentQuestionRubric(
                    question_id=question.id,
                    criterion_text=c.criterion_text.strip(),
                    max_marks=c.max_marks,
                    order_index=c.order_index if c.order_index is not None else idx,
                    criterion_embedding=crit_vec
                )
                db.add(rubric_row)

        db.commit()
        db.refresh(question)

    return {
        "message": "Question created successfully",
        "id": question.id,
        "assignment_id": question.assignment_id,
        "question_type": question.question_type,
        "max_marks": question.max_marks,
    }


# =========================================================================
# 2. GET EXAM QUESTIONS (Role-Based Sanitization)
# =========================================================================
@router.get("/assignments/{assignment_id}/questions")
def get_questions(assignment_id: int, user=Depends(get_user), db: Session = Depends(get_db)):
    assignment = db.query(Assignment).filter(Assignment.id == assignment_id).first()
    if not assignment:
        raise HTTPException(status_code=404, detail="Assessment not found")

    role = user["role"]
    if role == "student":
        enrollment = db.query(Enrollment).filter(
            Enrollment.student_id == user["id"],
            Enrollment.course_id == assignment.course_id
        ).first()
        if not enrollment:
            raise HTTPException(status_code=403, detail="You are not enrolled in this course")

    elif role == "teacher":
        course = db.query(Course).filter(Course.id == assignment.course_id).first()
        if not course or course.teacher_id != user["id"]:
            raise HTTPException(status_code=403, detail="Access denied")

    questions = db.query(AssessmentQuestion).filter(
        AssessmentQuestion.assignment_id == assignment.id
    ).order_by(AssessmentQuestion.order_index, AssessmentQuestion.id).all()

    result = []
    for q in questions:
        if role == "student":
            # =================================================================
            # CRITICAL STUDENT PRIVACY GUARANTEE:
            # - For MCQ: ONLY option id and option_text are returned.
            #   NEVER is_correct, NEVER correct_option_id.
            # - For Descriptive: ONLY question_text and max_marks are returned.
            #   NEVER reference_answer, NEVER reference_embedding.
            # =================================================================
            item = {
                "id": q.id,
                "question_text": q.question_text,
                "question_type": q.question_type,
                "max_marks": q.max_marks,
                "order_index": q.order_index,
            }
            if q.question_type == "mcq":
                opts = db.query(AssessmentQuestionOption).filter(
                    AssessmentQuestionOption.question_id == q.id
                ).order_by(AssessmentQuestionOption.order_index, AssessmentQuestionOption.id).all()
                item["options"] = [{"id": o.id, "option_text": o.option_text} for o in opts]
            result.append(item)
        else:
            # Teacher / Admin view with full keys and answers
            item = {
                "id": q.id,
                "question_text": q.question_text,
                "question_type": q.question_type,
                "max_marks": q.max_marks,
                "order_index": q.order_index,
                "correct_option_id": q.correct_option_id,
                "reference_answer": q.reference_answer,
            }
            if q.question_type == "mcq":
                opts = db.query(AssessmentQuestionOption).filter(
                    AssessmentQuestionOption.question_id == q.id
                ).order_by(AssessmentQuestionOption.order_index, AssessmentQuestionOption.id).all()
                item["options"] = [{
                    "id": o.id,
                    "option_text": o.option_text,
                    "is_correct": (o.id == q.correct_option_id)
                } for o in opts]
            elif q.question_type == "descriptive":
                rubrics = db.query(AssessmentQuestionRubric).filter(
                    AssessmentQuestionRubric.question_id == q.id
                ).order_by(AssessmentQuestionRubric.order_index, AssessmentQuestionRubric.id).all()
                item["rubric_criteria"] = [{
                    "id": r.id,
                    "criterion_text": r.criterion_text,
                    "max_marks": r.max_marks,
                    "order_index": r.order_index
                } for r in rubrics]
            result.append(item)

    return result


# =========================================================================
# 3. UPDATE EXAM QUESTION
# =========================================================================
@router.put("/assignments/{assignment_id}/questions/{question_id}")
def update_question(assignment_id: int, question_id: int, data: QuestionUpdate, user=Depends(get_user), db: Session = Depends(get_db)):
    if user["role"] not in ["teacher", "admin"]:
        raise HTTPException(status_code=403, detail="Teacher or admin access only")

    if user["role"] == "teacher":
        _check_teacher_owns_assignment(assignment_id, user["id"], db)

    q = db.query(AssessmentQuestion).filter(
        AssessmentQuestion.id == question_id,
        AssessmentQuestion.assignment_id == assignment_id
    ).first()
    if not q:
        raise HTTPException(status_code=404, detail="Question not found")

    if data.question_text is not None:
        text_val = data.question_text.strip()
        if not text_val:
            raise HTTPException(status_code=400, detail="Question text cannot be empty")
        q.question_text = text_val

    if data.max_marks is not None:
        if data.max_marks <= 0:
            raise HTTPException(status_code=400, detail="Maximum marks must be greater than zero")
        q.max_marks = data.max_marks

    if data.order_index is not None:
        q.order_index = data.order_index

    if q.question_type == "mcq" and data.options is not None:
        if len(data.options) < 2:
            raise HTTPException(status_code=400, detail="MCQ must have at least 2 options")
        correct_count = sum(1 for opt in data.options if opt.is_correct)
        if correct_count != 1:
            raise HTTPException(status_code=400, detail="MCQ must have exactly one correct option")

        # Delete existing options
        db.query(AssessmentQuestionOption).filter(AssessmentQuestionOption.question_id == q.id).delete()
        db.flush()

        correct_opt_id = None
        for idx, opt in enumerate(data.options):
            option_row = AssessmentQuestionOption(
                question_id=q.id,
                option_text=opt.option_text.strip(),
                order_index=opt.order_index or idx
            )
            db.add(option_row)
            db.flush()
            if opt.is_correct:
                correct_opt_id = option_row.id

        q.correct_option_id = correct_opt_id

    elif q.question_type == "descriptive":
        if data.reference_answer is not None:
            ref_ans = data.reference_answer.strip()
            if not ref_ans or len(ref_ans.split()) < 2:
                raise HTTPException(status_code=400, detail="Descriptive question requires a detailed reference answer")
            q.reference_answer = ref_ans
            q.reference_embedding = es.generate_embedding(ref_ans)

        target_max = data.max_marks if data.max_marks is not None else q.max_marks

        if data.rubric_criteria is not None:
            if len(data.rubric_criteria) > 0:
                crit_sum = sum(c.max_marks for c in data.rubric_criteria)
                if abs(crit_sum - float(target_max)) > 1e-4:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Rubric criteria marks total ({crit_sum}) must equal question maximum marks ({target_max})"
                    )
                for c in data.rubric_criteria:
                    if c.max_marks <= 0:
                        raise HTTPException(status_code=400, detail="Each rubric criterion must have max_marks > 0")
                    if not c.criterion_text or not c.criterion_text.strip():
                        raise HTTPException(status_code=400, detail="Rubric criterion text cannot be empty")

                # Remove old rubric criteria
                db.query(AssessmentQuestionRubric).filter(AssessmentQuestionRubric.question_id == q.id).delete()
                db.flush()

                for idx, c in enumerate(data.rubric_criteria):
                    crit_vec = es.generate_embedding(c.criterion_text.strip())
                    rubric_row = AssessmentQuestionRubric(
                        question_id=q.id,
                        criterion_text=c.criterion_text.strip(),
                        max_marks=c.max_marks,
                        order_index=c.order_index if c.order_index is not None else idx,
                        criterion_embedding=crit_vec
                    )
                    db.add(rubric_row)
            else:
                db.query(AssessmentQuestionRubric).filter(AssessmentQuestionRubric.question_id == q.id).delete()

    db.commit()
    db.refresh(q)
    return {"message": "Question updated successfully", "id": q.id}


# =========================================================================
# SUGGEST RUBRIC CRITERIA FROM REFERENCE ANSWER (AI Enhancement)
# =========================================================================
@router.post("/assignments/{assignment_id}/questions/suggest-rubric")
def suggest_rubric(assignment_id: int, data: RubricSuggestionRequest, user=Depends(get_user), db: Session = Depends(get_db)):
    if user["role"] not in ["teacher", "admin"]:
        raise HTTPException(status_code=403, detail="Teacher or admin access only")

    if user["role"] == "teacher":
        _check_teacher_owns_assignment(assignment_id, user["id"], db)

    ref_ans = (data.reference_answer or "").strip()
    if not ref_ans or len(ref_ans.split()) < 2:
        raise HTTPException(status_code=400, detail="Reference answer must have at least 2 words to suggest a rubric")

    max_marks = data.max_marks if data.max_marks > 0 else 10
    criteria = es.suggest_rubric_from_reference_answer(data.question_text, ref_ans, max_marks)
    return {"criteria": criteria}


# =========================================================================
# 4. DELETE EXAM QUESTION
# =========================================================================
@router.delete("/assignments/{assignment_id}/questions/{question_id}")
def delete_question(assignment_id: int, question_id: int, user=Depends(get_user), db: Session = Depends(get_db)):
    if user["role"] not in ["teacher", "admin"]:
        raise HTTPException(status_code=403, detail="Teacher or admin access only")

    if user["role"] == "teacher":
        _check_teacher_owns_assignment(assignment_id, user["id"], db)

    q = db.query(AssessmentQuestion).filter(
        AssessmentQuestion.id == question_id,
        AssessmentQuestion.assignment_id == assignment_id
    ).first()
    if not q:
        raise HTTPException(status_code=404, detail="Question not found")

    db.delete(q)
    db.commit()
    return {"message": "Question deleted successfully"}


# =========================================================================
# 5. CORE EVALUATION ENGINE (Invoked upon exam submission)
# =========================================================================
def evaluate_and_record_exam(
    assignment: Assignment,
    student_id: int,
    answers_map: dict[int, dict],
    db: Session
) -> tuple[Submission, list[StudentQuestionAnswer]]:
    """
    Server-authoritative evaluation:
    - Evaluates all MCQ questions via relational ID comparison (no pgvector).
    - Evaluates all Descriptive questions via pgvector cosine similarity in PostgreSQL.
    - Persists individual student_question_answers and overall submission.
    """
    now = datetime.now()
    questions = db.query(AssessmentQuestion).filter(
        AssessmentQuestion.assignment_id == assignment.id
    ).order_by(AssessmentQuestion.order_index, AssessmentQuestion.id).all()

    try:
        # Create submission record without premature commit
        submission = Submission(
            assignment_id=assignment.id,
            student_id=student_id,
            answer="Exam auto-evaluated",
            marks=0
        )
        db.add(submission)
        db.flush()

        total_awarded = 0.0
        recorded_answers = []

        for q in questions:
            ans_data = answers_map.get(q.id, {})

            if q.question_type == "mcq":
                selected_opt_id = ans_data.get("selected_option_id")
                if selected_opt_id is not None:
                    # Validate that selected_opt_id actually belongs to this question
                    opt = db.query(AssessmentQuestionOption).filter(
                        AssessmentQuestionOption.id == selected_opt_id,
                        AssessmentQuestionOption.question_id == q.id
                    ).first()
                    if not opt:
                        raise HTTPException(
                            status_code=400,
                            detail=f"Selected option {selected_opt_id} does not belong to question {q.id}"
                        )

                marks, is_correct, status = es.evaluate_mcq_answer(
                    selected_opt_id,
                    q.correct_option_id,
                    q.max_marks
                )
                sqa = StudentQuestionAnswer(
                    submission_id=submission.id,
                    question_id=q.id,
                    student_id=student_id,
                    question_type="mcq",
                    selected_option_id=selected_opt_id,
                    is_correct=is_correct,
                    student_answer=None,
                    reference_answer=None,
                    similarity_score=None,
                    awarded_marks=marks,
                    max_marks=q.max_marks,
                    evaluation_status=status,
                    evaluated_at=now,
                    evaluator_version="deterministic-mcq",
                    evaluator_confidence=1.0,
                    review_status="auto_finalized"
                )
                db.add(sqa)
                recorded_answers.append(sqa)
                total_awarded += marks

            elif q.question_type == "descriptive":
                raw_answer = ans_data.get("student_answer") or ""
                clean_ans = raw_answer.strip()

                rubrics = db.query(AssessmentQuestionRubric).filter(
                    AssessmentQuestionRubric.question_id == q.id
                ).order_by(AssessmentQuestionRubric.order_index, AssessmentQuestionRubric.id).all()

                if not clean_ans or len(clean_ans.split()) < 2:
                    # Unanswered or empty descriptive response -> 0 marks
                    empty_eval = {
                        "evaluator_version": "hybrid-v2-nli",
                        "embedding_model": "all-MiniLM-L6-v2",
                        "nli_model": "cross-encoder/nli-distilroberta-base",
                        "overall_semantic_similarity": 0.0,
                        "overall_correctness": 0.0,
                        "contradiction_detected": False,
                        "contradiction_details": [],
                        "evaluator_confidence": 0.99,
                        "review_status": "auto_finalized",
                        "criteria": []
                    }
                    sqa = StudentQuestionAnswer(
                        submission_id=submission.id,
                        question_id=q.id,
                        student_id=student_id,
                        question_type="descriptive",
                        student_answer=clean_ans,
                        reference_answer=None,
                        student_embedding=None,
                        similarity_score=0.0,
                        awarded_marks=0.0,
                        max_marks=q.max_marks,
                        evaluation_status="unanswered" if not clean_ans else "evaluated",
                        evaluated_at=now,
                        evaluator_version="hybrid-v2-nli",
                        evaluator_confidence=0.99,
                        review_status="auto_finalized",
                        rubric_evaluation=json.dumps(empty_eval)
                    )
                    db.add(sqa)
                    recorded_answers.append(sqa)
                else:
                    # Generate 384-dimensional vector embedding for student answer
                    stu_vec = es.generate_embedding(clean_ans)

                    # Ensure reference embedding exists in question record
                    if not q.reference_embedding and q.reference_answer:
                        q.reference_embedding = es.generate_embedding(q.reference_answer)
                        db.add(q)
                        db.flush()

                    ref_vec = list(q.reference_embedding) if q.reference_embedding else None

                    # Hybrid evaluation combining pgvector similarity + rubric criteria + NLI + contradiction check
                    awarded_marks, sim, eval_dict = es.evaluate_hybrid_descriptive(
                        db, clean_ans, q.max_marks, q.reference_answer, ref_vec, rubrics
                    )

                    sqa = StudentQuestionAnswer(
                        submission_id=submission.id,
                        question_id=q.id,
                        student_id=student_id,
                        question_type="descriptive",
                        student_answer=clean_ans,
                        reference_answer=None,
                        student_embedding=stu_vec,
                        similarity_score=sim,
                        awarded_marks=awarded_marks,
                        max_marks=q.max_marks,
                        evaluation_status="evaluated",
                        evaluated_at=now,
                        evaluator_version="hybrid-v2-nli",
                        evaluator_confidence=eval_dict.get("evaluator_confidence", 0.85),
                        review_status=eval_dict.get("review_status", "auto_finalized"),
                        rubric_evaluation=json.dumps(eval_dict)
                    )
                    db.add(sqa)
                    recorded_answers.append(sqa)
                    total_awarded += awarded_marks

        total_max = sum(q.max_marks for q in questions)
        rounded_marks = min(total_max, max(0, int(round(total_awarded))))
        submission.marks = rounded_marks
        submission.answer = f"Exam auto-evaluated. Total: {rounded_marks}/{total_max}"
        db.commit()
        db.refresh(submission)

        return submission, recorded_answers

    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Exam evaluation transaction failed: {str(e)}")


# =========================================================================
# 6. STUDENT EXAM SUBMISSION ENDPOINT (JSON)
# =========================================================================
@router.post("/assignments/{assignment_id}/submit-exam")
def submit_exam(assignment_id: int, data: ExamSubmissionCreate, user=Depends(get_user), db: Session = Depends(get_db)):
    if user["role"] != "student":
        raise HTTPException(status_code=403, detail="Student access only")

    assignment = db.query(Assignment).filter(Assignment.id == assignment_id).first()
    if not assignment:
        raise HTTPException(status_code=404, detail="Assessment not found")

    enrollment = db.query(Enrollment).filter(
        Enrollment.student_id == user["id"],
        Enrollment.course_id == assignment.course_id
    ).first()
    if not enrollment:
        raise HTTPException(status_code=403, detail="You are not enrolled in this course")

    now = datetime.now()
    if assignment.start_time and now < assignment.start_time:
        raise HTTPException(status_code=400, detail="This assessment is not open yet")
    
    deadline = _assessment_deadline(assignment)
    if deadline and now >= deadline:
        raise HTTPException(status_code=400, detail="Submission deadline has passed")

    existing = db.query(Submission).filter(
        Submission.assignment_id == assignment.id,
        Submission.student_id == user["id"]
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="You have already submitted this assessment")

    questions = db.query(AssessmentQuestion).filter(
        AssessmentQuestion.assignment_id == assignment.id
    ).order_by(AssessmentQuestion.order_index, AssessmentQuestion.id).all()
    q_dict = {q.id: q for q in questions}

    valid_q_ids = set(q_dict.keys())
    seen_q_ids = set()
    for ans in data.answers:
        if ans.question_id not in valid_q_ids:
            raise HTTPException(status_code=400, detail=f"Question {ans.question_id} does not belong to this assessment")
        if ans.question_id in seen_q_ids:
            raise HTTPException(status_code=400, detail=f"Duplicate answer submitted for question {ans.question_id}")
        seen_q_ids.add(ans.question_id)

    # Map student answers by question_id
    answers_map = {
        ans.question_id: {
            "selected_option_id": ans.selected_option_id,
            "student_answer": ans.student_answer
        }
        for ans in data.answers
    }

    submission, recorded_answers = evaluate_and_record_exam(assignment, user["id"], answers_map, db)

    total_max = sum(q.max_marks for q in questions)

    # =========================================================================
    # CRITICAL STUDENT PRIVACY:
    # Student receives ONLY awarded marks, max marks, total score, and pass/fail.
    # NEVER expose similarity scores, embeddings, reference answers, or reasoning!
    # =========================================================================
    return {
        "message": "Exam submitted and evaluated successfully",
        "submission_id": submission.id,
        "assignment_id": assignment.id,
        "total_marks": submission.marks,
        "max_marks": total_max,
        "percentage": round((submission.marks / total_max) * 100, 1) if total_max > 0 else 0,
        "status": "Passed" if (total_max > 0 and (submission.marks / total_max) >= 0.40) else ("Failed" if total_max > 0 else "Completed"),
        "questions": [
            {
                "question_id": sqa.question_id,
                "question_text": q_dict.get(sqa.question_id).question_text if q_dict.get(sqa.question_id) else "",
                "question_type": sqa.question_type,
                "max_marks": sqa.max_marks,
                "awarded_marks": sqa.awarded_marks
            }
            for sqa in recorded_answers
        ]
    }


# =========================================================================
# 7. SUBMISSION EVALUATION DETAILS (Strict Role Separation)
# =========================================================================
@router.get("/submissions/{submission_id}/evaluation")
def get_submission_evaluation(submission_id: int, user=Depends(get_user), db: Session = Depends(get_db)):
    submission = db.query(Submission).filter(Submission.id == submission_id).first()
    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found")

    role = user["role"]
    if role == "student":
        if submission.student_id != user["id"]:
            raise HTTPException(status_code=403, detail="Access denied")
    elif role == "teacher":
        assignment = db.query(Assignment).filter(Assignment.id == submission.assignment_id).first()
        if not assignment:
            raise HTTPException(status_code=404, detail="Assessment not found")
        course = db.query(Course).filter(Course.id == assignment.course_id).first()
        if not course or course.teacher_id != user["id"]:
            raise HTTPException(status_code=403, detail="Access denied")
    elif role != "admin":
        raise HTTPException(status_code=403, detail="Access denied")

    records = db.query(StudentQuestionAnswer).filter(
        StudentQuestionAnswer.submission_id == submission.id
    ).all()
    q_ids = [r.question_id for r in records]
    questions = {q.id: q for q in db.query(AssessmentQuestion).filter(AssessmentQuestion.id.in_(q_ids)).all()}

    total_max = sum(r.max_marks for r in records)

    if role == "student":
        # =====================================================================
        # STUDENT VIEW: Strip all internal similarity, vectors, and reference keys
        # Strict isolation: Never leak similarity, NLI, confidence, or review notes!
        # =====================================================================
        return {
            "submission_id": submission.id,
            "assignment_id": submission.assignment_id,
            "total_marks": submission.marks,
            "max_marks": total_max,
            "percentage": round((submission.marks / total_max) * 100, 1) if total_max > 0 else 0,
            "status": "Passed" if (total_max > 0 and (submission.marks / total_max) >= 0.40) else ("Failed" if total_max > 0 else "Completed"),
            "questions": [
                {
                    "question_id": r.question_id,
                    "question_text": questions.get(r.question_id).question_text if questions.get(r.question_id) else "",
                    "question_type": r.question_type,
                    "max_marks": r.max_marks,
                    "awarded_marks": r.teacher_override_marks if r.teacher_override_marks is not None else r.awarded_marks
                }
                for r in records
            ]
        }
    else:
        # =====================================================================
        # TEACHER / ADMIN AUDIT VIEW: Includes similarity score, reference answer,
        # student answer, correct keys, evaluation status, rubric breakdown, version,
        # NLI metrics, confidence score, and human review status.
        # =====================================================================
        return {
            "submission_id": submission.id,
            "assignment_id": submission.assignment_id,
            "student_id": submission.student_id,
            "total_marks": submission.marks,
            "max_marks": total_max,
            "questions": [
                {
                    "question_id": r.question_id,
                    "question_text": questions.get(r.question_id).question_text if questions.get(r.question_id) else "",
                    "question_type": r.question_type,
                    "max_marks": r.max_marks,
                    "awarded_marks": r.awarded_marks,
                    "teacher_override_marks": r.teacher_override_marks,
                    "teacher_review_note": r.teacher_review_note,
                    "review_status": r.review_status,
                    "evaluator_confidence": r.evaluator_confidence,
                    "reviewed_at": r.reviewed_at.isoformat() if r.reviewed_at else None,
                    "reviewed_by": r.reviewed_by,
                    "similarity_score": r.similarity_score,
                    "student_answer": r.student_answer,
                    "reference_answer": questions.get(r.question_id).reference_answer if questions.get(r.question_id) else None,
                    "selected_option_id": r.selected_option_id,
                    "correct_option_id": questions.get(r.question_id).correct_option_id if questions.get(r.question_id) else None,
                    "is_correct": r.is_correct,
                    "evaluation_status": r.evaluation_status,
                    "evaluated_at": r.evaluated_at.isoformat() if r.evaluated_at else None,
                    "evaluator_version": r.evaluator_version,
                    "rubric_evaluation": json.loads(r.rubric_evaluation) if r.rubric_evaluation else None
                }
                for r in records
            ]
        }


# =========================================================================
# 8. TEACHER: REVIEW & OVERRIDE EXAM EVALUATION
# =========================================================================
@router.post("/submissions/{submission_id}/review")
def review_submission(
    submission_id: int,
    data: TeacherReviewRequest,
    user=Depends(get_user),
    db: Session = Depends(get_db)
):
    if user["role"] not in ["teacher", "admin"]:
        raise HTTPException(status_code=403, detail="Teacher or admin access only")

    submission = db.query(Submission).filter(Submission.id == submission_id).first()
    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found")

    assignment = db.query(Assignment).filter(Assignment.id == submission.assignment_id).first()
    if not assignment:
        raise HTTPException(status_code=404, detail="Assessment not found")

    if user["role"] == "teacher":
        course = db.query(Course).filter(Course.id == assignment.course_id).first()
        if not course or course.teacher_id != user["id"]:
            raise HTTPException(status_code=403, detail="You can only review submissions for your own courses")

    records = db.query(StudentQuestionAnswer).filter(
        StudentQuestionAnswer.submission_id == submission.id
    ).all()
    records_by_qid = {r.question_id: r for r in records}

    now = datetime.now()
    for item in data.reviews:
        if item.question_id not in records_by_qid:
            raise HTTPException(status_code=400, detail=f"Question {item.question_id} does not belong to this submission")

        sqa = records_by_qid[item.question_id]
        if item.override_marks is not None:
            if item.override_marks < 0.0 or item.override_marks > sqa.max_marks:
                raise HTTPException(
                    status_code=400,
                    detail=f"Override marks must be between 0 and maximum marks ({sqa.max_marks})"
                )
            sqa.teacher_override_marks = float(round(item.override_marks, 2))

        if item.review_note is not None:
            sqa.teacher_review_note = item.review_note.strip()

        sqa.review_status = "reviewed"
        sqa.reviewed_at = now
        sqa.reviewed_by = user["id"]

    # Server-authoritative total marks recalculation
    total_max = sum(r.max_marks for r in records)
    total_awarded = sum(
        (r.teacher_override_marks if r.teacher_override_marks is not None else r.awarded_marks)
        for r in records
    )
    rounded_marks = min(total_max, max(0, int(round(total_awarded))))
    submission.marks = rounded_marks
    submission.answer = f"Exam auto-evaluated (Teacher Reviewed). Total: {rounded_marks}/{total_max}"

    db.commit()
    db.refresh(submission)

    return {
        "message": "Submission evaluation reviewed and updated successfully",
        "submission_id": submission.id,
        "total_marks": submission.marks,
        "max_marks": total_max,
        "review_status": "reviewed",
        "reviewed_at": now.isoformat()
    }

