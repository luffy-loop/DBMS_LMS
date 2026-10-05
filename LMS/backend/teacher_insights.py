from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from models import Course, Assignment, Submission
from auth import get_user

router = APIRouter()

@router.get("/teacher/insights")
def teacher_insights(user=Depends(get_user), db: Session = Depends(get_db)):
    if user["role"] != "teacher":
        raise HTTPException(status_code=403, detail="Teacher access only")
    courses = db.query(Course).filter(Course.teacher_id == user["id"]).all()
    assignments = db.query(Assignment).filter(Assignment.teacher_id == user["id"]).all()
    aids = [a.id for a in assignments]
    submissions = (
        db.query(Submission.id, Submission.assignment_id, Submission.marks)
        .filter(Submission.assignment_id.in_(aids))
        .all()
        if aids else []
    )
    graded = [s for s in submissions if s.marks is not None]
    rows = []
    for c in courses:
        ca = [a for a in assignments if a.course_id == c.id]
        ids = {a.id for a in ca}
        cs = [s for s in submissions if s.assignment_id in ids]
        cg = [s for s in cs if s.marks is not None]
        avg = round(sum(s.marks for s in cg) / len(cg), 1) if cg else None
        rows.append({
            "id": c.id,
            "title": c.title,
            "assessments": len(ca),
            "submissions": len(cs),
            "graded": len(cg),
            "pending": len(cs) - len(cg),
            "average": avg
        })
    rows.sort(key=lambda x: (x["average"] is None, x["average"] if x["average"] is not None else 999))
    return {
        "courses": len(courses),
        "assessments": len(assignments),
        "submissions": len(submissions),
        "graded": len(graded),
        "pending_grading": len(submissions) - len(graded),
        "average_marks": round(sum(s.marks for s in graded) / len(graded), 1) if graded else None,
        "grading_rate": round(len(graded) / len(submissions) * 100) if submissions else 0,
        "course_stats": rows,
        "focus_course": rows[0]["title"] if rows else None
    }
