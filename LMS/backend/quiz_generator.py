import json
from datetime import datetime
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from auth import get_user
from database import get_db
from models import AIJob, Assignment, AssessmentQuestion, AssessmentQuestionOption, Enrollment, Course
from notification_service import notify_users
from ai_jobs import create_job, run_quiz_job

router = APIRouter(prefix="/quiz", tags=["quiz"])


class QuizGenerateRequest(BaseModel):
    course_id: int
    question_count: int = Field(default=5, ge=1, le=10)


class QuizQuestionPublish(BaseModel):
    id: int
    question: str = Field(min_length=1, max_length=2000)
    options: list[str] = Field(min_length=2, max_length=6)
    answer: str = Field(min_length=1, max_length=1000)
    max_marks: int = Field(default=1, ge=1, le=100)
    explanation: str = Field(default="", max_length=2000)


class QuizAssignmentRequest(BaseModel):
    course_id: int
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=2000)
    start_time: datetime | None = None
    end_time: datetime | None = None
    duration_minutes: int | None = Field(default=None, gt=0)
    questions: list[QuizQuestionPublish] | None = None


def _can_access_course(user, course_id, db):
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    if user["role"] == "teacher" and course.teacher_id != user["id"]:
        raise HTTPException(status_code=403, detail="You can only use your own course")
    if user["role"] == "student" and not db.query(Enrollment.id).filter(Enrollment.student_id == user["id"], Enrollment.course_id == course_id).first():
        raise HTTPException(status_code=403, detail="You are not enrolled in this course")
    return course


@router.post("/generate")
def generate_quiz(data: QuizGenerateRequest, background_tasks: BackgroundTasks, user=Depends(get_user), db: Session = Depends(get_db)):
    if user["role"] not in {"student", "teacher", "admin"}:
        raise HTTPException(status_code=403, detail="Access denied")
    course = _can_access_course(user, data.course_id, db)
    job = create_job(db, user["id"], course.id, "quiz", {"query": "key concepts important definitions", "question_count": data.question_count})
    background_tasks.add_task(run_quiz_job, job.id)
    return {"job_id": job.job_id, "status": job.status}


@router.get("/jobs/{job_id}")
def quiz_job_status(job_id: str, user=Depends(get_user), db: Session = Depends(get_db)):
    job = db.query(AIJob).filter(AIJob.job_id == job_id, AIJob.user_id == user["id"], AIJob.job_type == "quiz").first()
    if not job:
        raise HTTPException(status_code=404, detail="Quiz job not found")
    return {"job_id":job.job_id,"status":job.status,"result":json.loads(job.result) if job.result else None,"error":json.loads(job.error) if job.error and job.error.startswith("{") else job.error,"created_at":job.created_at.isoformat(),"updated_at":job.updated_at.isoformat()}


@router.post("/jobs/{job_id}/cancel")
def cancel_quiz_job(job_id: str, user=Depends(get_user), db: Session = Depends(get_db)):
    job = db.query(AIJob).filter(AIJob.job_id == job_id, AIJob.user_id == user["id"], AIJob.job_type == "quiz").first()
    if not job:
        raise HTTPException(status_code=404, detail="Quiz job not found")
    if job.status in {"COMPLETED","FAILED","CANCELLED"}:
        return {"job_id":job.job_id,"status":job.status}
    job.status="CANCELLED"
    db.commit()
    return {"job_id":job.job_id,"status":"CANCELLED"}


@router.post("/jobs/{job_id}/assignment")
def create_assignment_from_quiz(job_id: str, data: QuizAssignmentRequest, user=Depends(get_user), db: Session = Depends(get_db)):
    if user["role"] != "teacher":
        raise HTTPException(status_code=403, detail="Teacher access only")
    job = db.query(AIJob).filter(AIJob.job_id == job_id, AIJob.user_id == user["id"], AIJob.job_type == "quiz").first()
    if not job:
        raise HTTPException(status_code=404, detail="Quiz job not found")
    if job.status != "COMPLETED" or not job.result:
        raise HTTPException(status_code=409, detail="Quiz must be completed before publishing")
    if job.assignment_id:
        return {"message":"Assignment already created","assignment_id":job.assignment_id}
    course = _can_access_course(user, data.course_id, db)
    if course.id != job.course_id:
        raise HTTPException(status_code=400, detail="Assignment course must match the generated quiz course")
    payload=json.loads(job.result)
    questions=data.questions or [QuizQuestionPublish(**q) for q in payload.get("questions",[])]
    if not questions:
        raise HTTPException(status_code=400, detail="Generated quiz has no questions")
    if any(len(q.options) < 2 or q.answer not in q.options for q in questions):
        raise HTTPException(status_code=422, detail="Each question must have at least two options and a valid correct answer")
    if data.start_time and data.end_time and data.end_time <= data.start_time:
        raise HTTPException(status_code=422, detail="Due time must be after start time")

    assignment=Assignment(
        title=data.title.strip(),
        description=data.description.strip() or "AI-generated quiz reviewed and published by the teacher.",
        course_id=course.id,
        teacher_id=user["id"],
        type="test",
        start_time=data.start_time,
        end_time=data.end_time,
        duration_minutes=data.duration_minutes,
    )
    db.add(assignment)
    db.flush()
    for index, question in enumerate(questions):
        aq=AssessmentQuestion(
            assignment_id=assignment.id,
            question_text=question.question.strip(),
            question_type="mcq",
            max_marks=question.max_marks,
            order_index=index,
            reference_answer=question.explanation,
        )
        db.add(aq)
        db.flush()
        for option_index, option in enumerate(question.options):
            row=AssessmentQuestionOption(question_id=aq.id,option_text=option.strip(),order_index=option_index)
            db.add(row)
            db.flush()
            if option.strip()==question.answer.strip():
                aq.correct_option_id=row.id
        if aq.correct_option_id is None:
            raise HTTPException(status_code=422, detail="A question is missing its correct option")
    student_ids=[row[0] for row in db.query(Enrollment.student_id).filter(Enrollment.course_id==course.id).all()]
    notify_users(db,student_ids,"assignment_created","New assignment",assignment.title+" is now available in "+course.title+".","assignment",assignment.id)
    job.assignment_id=assignment.id
    db.commit()
    return {"message":"Assignment published","assignment_id":assignment.id,"course_id":course.id}
