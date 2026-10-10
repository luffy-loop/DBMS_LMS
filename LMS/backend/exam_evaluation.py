import json
import re
from datetime import datetime, timedelta, timezone
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
from audit_log import record_audit
import evaluation_service as es

router = APIRouter(prefix="", tags=["exam_evaluation"])


def normalize_datetime(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is not None:
        return dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


def get_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def low_score_threshold() -> float:
    import os
    try:
        value = float(os.getenv("LOW_SCORE_REVIEW_THRESHOLD_PERCENT", "25"))
    except (TypeError, ValueError):
        value = 25.0
    return min(100.0, max(0.0, value))


def is_low_score(awarded: float, maximum: float, threshold: float | None = None) -> bool:
    from decimal import Decimal, InvalidOperation
    try:
        awarded_value = Decimal(str(awarded))
        maximum_value = Decimal(str(maximum))
        limit = Decimal(str(low_score_threshold() if threshold is None else min(100.0, max(0.0, float(threshold)))))
    except (InvalidOperation, TypeError, ValueError):
        return True
    if not awarded_value.is_finite() or not maximum_value.is_finite() or maximum_value <= 0:
        return False
    return awarded_value < maximum_value * limit / Decimal("100")


get_utc_now = get_now


def _assessment_deadline(assignment: Assignment):
    deadlines = []
    end = normalize_datetime(assignment.end_time)
    start = normalize_datetime(assignment.start_time)
    if end:
        deadlines.append(end)
    if start and assignment.duration_minutes and assignment.type in {"test", "exam"}:
        deadlines.append(start + timedelta(minutes=assignment.duration_minutes))
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

    q_ids = [q.id for q in questions]
    options_by_qid = {}
    if q_ids:
        all_opts = db.query(AssessmentQuestionOption).filter(
            AssessmentQuestionOption.question_id.in_(q_ids)
        ).order_by(AssessmentQuestionOption.order_index, AssessmentQuestionOption.id).all()
        for o in all_opts:
            options_by_qid.setdefault(o.question_id, []).append(o)

    rubrics_by_qid = {}
    if q_ids and role != "student":
        all_rubrics = db.query(AssessmentQuestionRubric).filter(
            AssessmentQuestionRubric.question_id.in_(q_ids)
        ).order_by(AssessmentQuestionRubric.order_index, AssessmentQuestionRubric.id).all()
        for r in all_rubrics:
            rubrics_by_qid.setdefault(r.question_id, []).append(r)

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
                opts = options_by_qid.get(q.id, [])
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
                opts = options_by_qid.get(q.id, [])
                item["options"] = [{
                    "id": o.id,
                    "option_text": o.option_text,
                    "is_correct": (o.id == q.correct_option_id)
                } for o in opts]
            elif q.question_type == "descriptive":
                rubrics = rubrics_by_qid.get(q.id, [])
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
    now = get_now()
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

        desc_q_ids = [q.id for q in questions if q.question_type == "descriptive"]
        rubrics_by_qid = {}
        if desc_q_ids:
            all_rubrics = db.query(AssessmentQuestionRubric).filter(
                AssessmentQuestionRubric.question_id.in_(desc_q_ids)
            ).order_by(AssessmentQuestionRubric.order_index, AssessmentQuestionRubric.id).all()
            for r in all_rubrics:
                rubrics_by_qid.setdefault(r.question_id, []).append(r)

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
                    review_status="ai_evaluated"
                )
                db.add(sqa)
                recorded_answers.append(sqa)
                total_awarded += marks

            elif q.question_type == "descriptive":
                raw_answer = ans_data.get("student_answer") or ""
                clean_ans = raw_answer.strip()

                rubrics = rubrics_by_qid.get(q.id, [])

                if not clean_ans or len(clean_ans.split()) < 2:
                    manual_review_required = bool(ans_data.get("manual_review_required"))
                    empty_eval = {
                        "evaluator_version": "hybrid-v2-nli",
                        "embedding_model": "all-MiniLM-L6-v2",
                        "nli_model": "cross-encoder/nli-distilroberta-base",
                        "overall_semantic_similarity": 0.0,
                        "overall_correctness": 0.0,
                        "contradiction_detected": False,
                        "contradiction_details": [],
                        "evaluator_confidence": 0.0 if manual_review_required else 0.99,
                        "review_status": "needs_review" if manual_review_required else "auto_finalized",
                        "feedback": "PDF text could not be extracted reliably. Please review the uploaded file manually." if manual_review_required else "No substantive answer was provided.",
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
                        evaluation_status="evaluation_failed" if manual_review_required else ("unanswered" if not clean_ans else "evaluated"),
                        evaluated_at=now,
                        evaluator_version="hybrid-v2-nli",
                        evaluator_confidence=0.0 if manual_review_required else 0.99,
                        review_status="needs_review" if manual_review_required else "auto_finalized",
                        rubric_evaluation=json.dumps(empty_eval)
                    )
                    db.add(sqa)
                    recorded_answers.append(sqa)
                else:
                    try:
                        if not q.reference_answer or len(q.reference_answer.strip().split()) < 2:
                            raise ValueError("reference_answer_missing")
                        stu_vec = es.generate_embedding(clean_ans)
                        if not q.reference_embedding:
                            q.reference_embedding = es.generate_embedding(q.reference_answer)
                            db.add(q)
                            db.flush()
                        ref_vec = list(q.reference_embedding) if q.reference_embedding else None
                        awarded_marks, sim, eval_dict = es.evaluate_hybrid_descriptive(
                            db, clean_ans, q.max_marks, q.reference_answer, ref_vec, rubrics
                        )
                        if not isinstance(eval_dict, dict) or eval_dict.get("fallback_error"):
                            raise RuntimeError("evaluation_unavailable")
                        criteria = eval_dict.get("criteria") or []
                        eval_dict["matched_concepts"] = [
                            str(item.get("criterion_text")) for item in criteria
                            if isinstance(item, dict) and item.get("covered") and item.get("criterion_text")
                        ]
                        eval_dict["missing_concepts"] = [
                            str(item.get("criterion_text")) for item in criteria
                            if isinstance(item, dict) and not item.get("covered") and item.get("criterion_text")
                        ]
                        eval_dict["feedback"] = (
                            "Your answer covers the key ideas."
                            if not eval_dict["missing_concepts"]
                            else "Review the missing criteria: " + ", ".join(eval_dict["missing_concepts"][:4]) + "."
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
                            awarded_marks=max(0.0, min(float(q.max_marks), float(awarded_marks))),
                            max_marks=q.max_marks,
                            evaluation_status="evaluated",
                            evaluated_at=now,
                            evaluator_version="hybrid-v2-nli",
                            evaluator_confidence=eval_dict.get("evaluator_confidence"),
                            review_status="needs_review" if eval_dict.get("review_status") in {"review_required", "review_recommended"} else "ai_evaluated",
                            rubric_evaluation=json.dumps(eval_dict)
                        )
                        total_awarded += sqa.awarded_marks
                    except Exception as exc:
                        logger = __import__("logging").getLogger("lms.exam_evaluation")
                        logger.warning("Descriptive evaluation unavailable question_id=%s error_type=%s", q.id, type(exc).__name__)
                        sqa = StudentQuestionAnswer(
                            submission_id=submission.id,
                            question_id=q.id,
                            student_id=student_id,
                            question_type="descriptive",
                            student_answer=clean_ans,
                            reference_answer=None,
                            student_embedding=None,
                            similarity_score=None,
                            awarded_marks=0.0,
                            max_marks=q.max_marks,
                            evaluation_status="evaluation_failed",
                            evaluated_at=now,
                            evaluator_version="hybrid-v2-nli",
                            evaluator_confidence=None,
                            review_status="needs_review",
                            rubric_evaluation=json.dumps({
                                "summary": "Automated evaluation was unavailable. Teacher review is required.",
                                "feedback": "This answer needs manual review because automated evaluation could not complete.",
                                "criteria": [],
                                "matched_concepts": [],
                                "missing_concepts": [],
                                "error_type": type(exc).__name__,
                            })
                        )
                    db.add(sqa)
                    recorded_answers.append(sqa)

        total_max = sum(q.max_marks for q in questions)
        rounded_marks = round(min(float(total_max), max(0.0, float(total_awarded))), 2)
        failed_evaluation = any(row.evaluation_status == "evaluation_failed" for row in recorded_answers)
        if total_max > 0 and is_low_score(total_awarded, total_max):
            for row in recorded_answers:
                if row.review_status != "evaluation_failed":
                    row.review_status = "needs_review"
        # Aggregate AI marks remain suggestions on question rows until a teacher reviews.
        submission.marks = None
        submission.marks_published = False
        submission.graded_by = None
        submission.graded_at = None
        submission.answer = "Exam submission received."
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

    now = get_now()
    start = normalize_datetime(assignment.start_time)
    if start and now < start:
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

    try:
        submission, recorded_answers = evaluate_and_record_exam(assignment, user["id"], answers_map, db)
    except HTTPException as exc:
        if exc.status_code == 500 and db.query(Submission.id).filter(
            Submission.assignment_id == assignment.id,
            Submission.student_id == user["id"],
        ).first():
            raise HTTPException(status_code=409, detail="You have already submitted this assessment") from exc
        raise

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
        "total_marks": None,
        "max_marks": total_max,
        "percentage": None,
        "status": "awaiting_teacher_review",
        "marks_published": False,
        "questions": [
            {
                "question_id": sqa.question_id,
                "question_text": q_dict.get(sqa.question_id).question_text if q_dict.get(sqa.question_id) else "",
                "question_type": sqa.question_type,
                "max_marks": sqa.max_marks,
                "awarded_marks": None
            }
            for sqa in recorded_answers
        ]
    }


# =========================================================================
# 7. SUBMISSION EVALUATION DETAILS (Strict Role Separation)
# =========================================================================
@router.post("/submissions/{submission_id}/correct-with-ai")
def correct_submission_with_ai(submission_id: int, user=Depends(get_user), db: Session = Depends(get_db)):
    if user["role"] not in {"teacher", "admin"}:
        raise HTTPException(status_code=403, detail="Teacher or admin access only")

    submission = db.query(Submission).filter(Submission.id == submission_id).with_for_update().first()
    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found")

    if user["role"] == "teacher":
        assignment, _ = _check_teacher_owns_assignment(submission.assignment_id, user["id"], db)
    else:
        assignment = db.query(Assignment).filter(Assignment.id == submission.assignment_id).first()
        if not assignment:
            raise HTTPException(status_code=404, detail="Assessment not found")

    records = db.query(StudentQuestionAnswer).filter(
        StudentQuestionAnswer.submission_id == submission.id
    ).all()
    if not records:
        # Legacy free-text submissions can be mapped safely only when the assessment
        # has exactly one descriptive question with a usable reference answer.
        legacy_questions = db.query(AssessmentQuestion).filter(
            AssessmentQuestion.assignment_id == assignment.id,
            AssessmentQuestion.question_type == "descriptive",
        ).order_by(AssessmentQuestion.order_index, AssessmentQuestion.id).all()
        answer_text = (submission.answer or "").strip()
        if len(legacy_questions) != 1 or len(answer_text.split()) < 2:
            raise HTTPException(
                status_code=422,
                detail="This submission cannot be graded automatically: a substantive answer and exactly one matching descriptive question are required. Add question-level answers or grade it manually."
            )
        legacy_question = legacy_questions[0]
        if len((legacy_question.reference_answer or "").split()) < 2:
            raise HTTPException(status_code=422, detail="Add a reference answer or rubric to this question before using AI grading. The original submission is preserved.")
        legacy_record = StudentQuestionAnswer(
            submission_id=submission.id,
            question_id=legacy_question.id,
            student_id=submission.student_id,
            question_type="descriptive",
            student_answer=answer_text,
            reference_answer=legacy_question.reference_answer,
            awarded_marks=0,
            max_marks=int(legacy_question.max_marks or assignment.max_marks or 10),
            evaluation_status="pending",
            evaluated_at=get_now(),
            review_status="needs_review",
        )
        db.add(legacy_record)
        db.flush()
        records = [legacy_record]

    question_ids = [row.question_id for row in records]
    questions = {
        q.id: q for q in db.query(AssessmentQuestion)
        .filter(AssessmentQuestion.id.in_(question_ids), AssessmentQuestion.assignment_id == assignment.id)
        .all()
    }
    rubric_rows = db.query(AssessmentQuestionRubric).filter(
        AssessmentQuestionRubric.question_id.in_(question_ids)
    ).order_by(AssessmentQuestionRubric.order_index, AssessmentQuestionRubric.id).all()
    rubrics_by_qid = {}
    for rubric in rubric_rows:
        rubrics_by_qid.setdefault(rubric.question_id, []).append(rubric)

    # Reuse the persisted result on repeated successful requests. Failed rows remain retryable.
    if all(row.evaluation_status not in {"evaluation_failed", "pending"} for row in records) and any(
        row.evaluator_version and row.review_status in {"ai_evaluated", "needs_review"} for row in records
    ):
        total_max = sum(float(row.max_marks) for row in records)
        suggested = sum(float(row.awarded_marks) for row in records)
        return {
            "submission_id": submission.id,
            "suggested_marks": round(suggested, 2),
            "max_marks": total_max,
            "review_required": any(row.review_status == "needs_review" for row in records) or is_low_score(suggested, total_max),
            "already_evaluated": True,
            "questions": len(records),
            "message": "Saved AI suggestions loaded. Teacher review and publication are still required.",
        }

    failures = []
    for row in records:
        question = questions.get(row.question_id)
        if question is None:
            row.evaluation_status = "evaluation_failed"
            row.review_status = "needs_review"
            failures.append("A saved answer no longer matches an assessment question.")
            continue

        if question.question_type == "mcq":
            marks, correct, status = es.evaluate_mcq_answer(
                row.selected_option_id, question.correct_option_id, question.max_marks
            )
            row.awarded_marks = max(0.0, min(float(question.max_marks), float(marks)))
            row.is_correct = correct
            row.evaluation_status = status
            row.evaluator_version = "deterministic-mcq"
            row.evaluator_confidence = 1.0
            row.evaluated_at = get_now()
            row.review_status = "ai_evaluated"
            row.rubric_evaluation = json.dumps({
                "summary": "Graded against the saved correct option.",
                "feedback": "Correct answer." if correct else "Incorrect or unanswered.",
                "matched_concepts": [],
                "missing_concepts": [],
                "criteria": [],
            })
            continue

        student_answer = (row.student_answer or "").strip()
        reference_answer = (question.reference_answer or "").strip()
        if not student_answer or len(student_answer.split()) < 2:
            row.evaluation_status = "evaluation_failed"
            row.review_status = "needs_review"
            row.evaluator_confidence = 0.0
            row.rubric_evaluation = json.dumps({
                "summary": "A substantive answer is not available for automated evaluation.",
                "feedback": "Review the original submission manually.",
                "matched_concepts": [],
                "missing_concepts": [],
                "criteria": [],
            })
            failures.append("A descriptive answer is empty or too short for reliable evaluation.")
            continue
        if len(reference_answer.split()) < 2:
            row.evaluation_status = "evaluation_failed"
            row.review_status = "needs_review"
            row.evaluator_confidence = 0.0
            row.rubric_evaluation = json.dumps({
                "summary": "No teacher reference answer is configured.",
                "feedback": "Add a reference answer and marking rubric before running AI correction.",
                "matched_concepts": [],
                "missing_concepts": [],
                "criteria": [],
            })
            failures.append("A reference answer is missing for at least one descriptive question.")
            continue

        # Fast path for concise answers with strong lexical/concept overlap. This avoids
        # blocking on large embedding/NLI model downloads for simple answers while
        # keeping these model-light suggestions explicitly subject to teacher review.
        criteria_rows = rubrics_by_qid.get(question.id, [])
        if len(student_answer.split()) <= 20 and len(reference_answer.split()) <= 16:
            lexical_reference = es.calculate_lexical_answer_score(student_answer, reference_answer)
            contradiction, contradiction_details, _ = es.detect_contradictions_and_correctness(
                student_answer, reference_answer,
                [str(getattr(item, "criterion_text", "")) for item in criteria_rows]
            )
            if lexical_reference >= 0.50 and not contradiction:
                if criteria_rows:
                    criteria_results = []
                    awarded_total = 0.0
                    for criterion in criteria_rows:
                        criterion_text = str(getattr(criterion, "criterion_text", "") or "")
                        criterion_max = float(getattr(criterion, "max_marks", 1.0) or 1.0)
                        ratio = es.calculate_lexical_answer_score(student_answer, criterion_text)
                        awarded_criterion = round(max(0.0, min(criterion_max, ratio * criterion_max)), 2)
                        awarded_total += awarded_criterion
                        criteria_results.append({
                            "criterion_text": criterion_text,
                            "max_marks": criterion_max,
                            "awarded_marks": awarded_criterion,
                            "score_ratio": ratio,
                            "covered": ratio >= 0.50,
                            "method": "lexical_concept_overlap",
                        })
                    row.awarded_marks = max(0.0, min(float(question.max_marks), round(awarded_total, 1)))
                else:
                    criteria_results = []
                    row.awarded_marks = max(0.0, min(float(question.max_marks), round(lexical_reference * float(question.max_marks), 1)))
                reference_terms = list(dict.fromkeys(
                    re.findall(r"[a-z0-9]+(?:-[a-z0-9]+)?", reference_answer.lower())
                ))
                matched_terms = [term for term in reference_terms if re.search(r"(?<![a-z0-9])" + re.escape(term) + r"(?![a-z0-9])", student_answer.lower())]
                missing_terms = [term for term in reference_terms if term not in matched_terms and term not in {"is", "a", "an", "the", "of", "and", "to", "for"}]
                row.similarity_score = None
                row.student_embedding = None
                row.evaluation_status = "evaluated"
                row.evaluator_version = "lexical-short-answer-v1"
                row.evaluator_confidence = min(0.74, max(0.55, lexical_reference))
                row.evaluated_at = get_now()
                row.review_status = "needs_review"
                row.rubric_evaluation = json.dumps({
                    "summary": "A concise answer matched key concepts without a detected contradiction.",
                    "feedback": "Suggested partial/full credit is based on lexical concept overlap (" + str(round(lexical_reference * 100)) + "%). This fast path avoids waiting for semantic model startup; teacher review is required.",
                    "matched_concepts": matched_terms,
                    "missing_concepts": missing_terms,
                    "criteria": criteria_results,
                    "scoring_method": "lexical-short-answer-v1",
                    "review_reason": "Concise-answer fast path; teacher confirmation required.",
                })
                continue

        try:
            student_vector = es.generate_embedding(student_answer)
            if not question.reference_embedding:
                question.reference_embedding = es.generate_embedding(reference_answer)
                db.add(question)
                db.flush()
            awarded, similarity, evaluation = es.evaluate_hybrid_descriptive(
                db, student_answer, question.max_marks, reference_answer,
                list(question.reference_embedding) if question.reference_embedding else None,
                criteria_rows
            )
            if not isinstance(evaluation, dict) or evaluation.get("fallback_error"):
                raise RuntimeError("evaluation_unavailable")
            criteria = evaluation.get("criteria") or []
            matched = [
                str(item.get("criterion_text")) for item in criteria
                if isinstance(item, dict) and item.get("covered") and item.get("criterion_text")
            ]
            missing = [
                str(item.get("criterion_text")) for item in criteria
                if isinstance(item, dict) and not item.get("covered") and item.get("criterion_text")
            ]
            evaluation["matched_concepts"] = matched
            evaluation["missing_concepts"] = missing
            evaluation["feedback"] = (
                "Your answer covers the key ideas."
                if not missing else "Review the missing criteria: " + ", ".join(missing[:4]) + "."
            )
            row.awarded_marks = max(0.0, min(float(question.max_marks), float(awarded)))
            row.similarity_score = similarity
            row.student_embedding = student_vector
            row.evaluation_status = "evaluated"
            row.evaluator_version = "hybrid-v2-nli"
            row.evaluator_confidence = evaluation.get("evaluator_confidence")
            row.evaluated_at = get_now()
            row.review_status = "needs_review" if evaluation.get("review_status") in {"review_required", "review_recommended"} else "ai_evaluated"
            row.rubric_evaluation = json.dumps(evaluation)
        except Exception as exc:
            import logging
            logging.getLogger("lms.exam_evaluation").warning(
                "Teacher-triggered correction failed submission_id=%s question_id=%s error_type=%s",
                submission.id, row.question_id, type(exc).__name__
            )
            row.evaluation_status = "evaluation_failed"
            row.review_status = "needs_review"
            row.evaluator_confidence = None
            row.rubric_evaluation = json.dumps({
                "summary": "Automated evaluation was unavailable.",
                "feedback": "Retry AI correction or review this answer manually. No new score was fabricated.",
                "matched_concepts": [],
                "missing_concepts": [],
                "criteria": [],
                "error_type": type(exc).__name__,
            })
            failures.append("Automated evaluation failed for one or more descriptive answers.")

    total_max = sum(float(row.max_marks) for row in records)
    scored_records = [row for row in records if row.evaluation_status not in {"evaluation_failed", "pending"}]
    score_available = bool(scored_records)
    suggested_total = sum(float(row.awarded_marks) for row in scored_records)
    review_required = bool(failures) or any(row.review_status == "needs_review" for row in records)
    if score_available and is_low_score(suggested_total, total_max):
        review_required = True
        for row in records:
            if row.review_status != "needs_review":
                row.review_status = "needs_review"

    # AI evaluation only updates question-level suggestions and review state.
    # Preserve any teacher-finalized marks and publication state during re-evaluation.
    # A failed evaluation is not a zero-mark answer: do not report a score when no
    # question was evaluated successfully.
    db.commit()
    record_audit(db, user["id"], "assessment_ai_correction_completed", "submission", submission.id, {
        "assignment_id": assignment.id,
        "suggested_marks": round(suggested_total, 2) if score_available else None,
        "max_marks": total_max,
        "review_required": review_required,
        "evaluation_failures": len(failures),
    })
    return {
        "submission_id": submission.id,
        "suggested_marks": round(suggested_total, 2) if score_available else None,
        "max_marks": total_max,
        "review_required": review_required,
        "evaluation_failures": len(failures),
        "message": "AI suggestions saved. Teacher review and publication are still required." if score_available else "AI evaluation did not produce a reliable score. No marks were awarded; review the recorded failure reason and grade manually or retry.",
        "questions": len(records),
    }


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
            "total_marks": submission.marks if submission.marks_published else None,
            "max_marks": total_max,
            "percentage": round((submission.marks / total_max) * 100, 1) if submission.marks_published and submission.marks is not None and total_max > 0 else None,
            "status": "published" if submission.marks_published else ("awaiting_publication" if submission.marks is not None else "awaiting_teacher_review"),
            "marks_published": bool(submission.marks_published),
            "questions": [
                {
                    "question_id": r.question_id,
                    "question_text": questions.get(r.question_id).question_text if questions.get(r.question_id) else "",
                    "question_type": r.question_type,
                    "max_marks": r.max_marks,
                    "awarded_marks": (r.teacher_override_marks if r.teacher_override_marks is not None else r.awarded_marks) if submission.marks_published else None
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
            "marks_published": bool(submission.marks_published),
            "submission_answer": submission.answer,
            "teacher_review_note": submission.teacher_review_note,
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

    now = get_now()
    for item in data.reviews:
        if item.question_id not in records_by_qid:
            raise HTTPException(status_code=400, detail=f"Question {item.question_id} does not belong to this submission")
        sqa = records_by_qid[item.question_id]
        if item.override_marks is not None and (item.override_marks < 0.0 or item.override_marks > sqa.max_marks):
            raise HTTPException(status_code=400, detail=f"Override marks must be between 0 and maximum marks ({sqa.max_marks})")

    for item in data.reviews:
        sqa = records_by_qid[item.question_id]
        if item.override_marks is not None:
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
    rounded_marks = round(min(float(total_max), max(0.0, float(total_awarded))), 2)
    submission.marks = rounded_marks
    submission.marks_published = False
    submission.graded_by = user["id"]
    submission.graded_at = now
    submission.teacher_review_note = "; ".join(
        item.review_note.strip() for item in data.reviews if item.review_note and item.review_note.strip()
    )[:2000] or submission.teacher_review_note

    db.commit()
    db.refresh(submission)
    record_audit(db, user["id"], "assessment_submission_reviewed", "submission", submission.id, {
        "assignment_id": assignment.id,
        "total_marks": rounded_marks,
        "max_marks": total_max,
    })

    return {
        "message": "Submission evaluation reviewed and updated successfully",
        "submission_id": submission.id,
        "total_marks": submission.marks,
        "max_marks": total_max,
        "review_status": "reviewed",
        "reviewed_at": now.isoformat()
    }

