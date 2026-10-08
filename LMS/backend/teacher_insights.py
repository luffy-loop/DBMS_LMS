from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from database import get_db
from models import Course, Assignment, Submission, Enrollment
from auth import get_user

router = APIRouter()

@router.get("/teacher/insights")
def teacher_insights(user=Depends(get_user), db: Session = Depends(get_db)):
    if user["role"] != "teacher":
        raise HTTPException(status_code=403, detail="Teacher access only")
    courses = db.query(Course).filter(Course.teacher_id == user["id"]).all()
    assignments = db.query(Assignment).filter(Assignment.teacher_id == user["id"]).all()
    aids = [a.id for a in assignments]
    submissions = db.query(Submission.id, Submission.assignment_id, Submission.student_id, Submission.marks).filter(Submission.assignment_id.in_(aids)).all() if aids else []
    graded = [s for s in submissions if s.marks is not None]
    rows = []
    assessment_performance = []
    for c in courses:
        ca = [a for a in assignments if a.course_id == c.id]
        ids = {a.id for a in ca}
        cs = [s for s in submissions if s.assignment_id in ids]
        cg = [s for s in cs if s.marks is not None]
        enrolled = db.query(func.count(Enrollment.id)).filter(Enrollment.course_id == c.id).scalar() or 0
        possible = enrolled * len(ca)
        completion = round(len(cs) / possible * 100, 1) if possible else 0
        avg = round(sum(s.marks for s in cg) / len(cg), 1) if cg else None
        rows.append({"id": c.id, "title": c.title, "assessments": len(ca), "enrolled_students": enrolled, "submissions": len(cs), "graded": len(cg), "pending": len(cs) - len(cg), "average": avg, "completion_rate": completion})
        for a in ca:
            asubs = [s for s in cs if s.assignment_id == a.id]
            graded_a = [s for s in asubs if s.marks is not None]
            assessment_performance.append({"id": a.id, "title": a.title, "course_id": c.id, "submissions": len(asubs), "graded": len(graded_a), "average": round(sum(s.marks for s in graded_a) / len(graded_a), 1) if graded_a else None})
    rows.sort(key=lambda x: (x["average"] is None, x["average"] if x["average"] is not None else 999))
    total_possible = sum(r["enrolled_students"] * r["assessments"] for r in rows)
    completion_rate = round(len(submissions) / total_possible * 100, 1) if total_possible else 0
    return {"courses": len(courses), "assessments": len(assignments), "submissions": len(submissions), "graded": len(graded), "pending_grading": len(submissions) - len(graded), "average_marks": round(sum(s.marks for s in graded) / len(graded), 1) if graded else None, "grading_rate": round(len(graded) / len(submissions) * 100, 1) if submissions else 0, "completion_rate": completion_rate, "course_stats": rows, "assessment_performance": assessment_performance, "focus_course": rows[0]["title"] if rows else None}
