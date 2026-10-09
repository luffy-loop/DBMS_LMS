from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from auth import get_user
from database import get_db

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/course-performance")
def course_performance(user=Depends(get_user), db: Session = Depends(get_db)):
    if user["role"] not in ["teacher", "admin"]:
        raise HTTPException(status_code=403, detail="Teacher or admin access only")

    rows = db.execute(text("""
        SELECT course_id, course_title, enrolled_students,
               submissions, average_marks, graded_students
        FROM course_performance
        ORDER BY course_id
    """)).mappings().all()

    return {"courses": [dict(row) for row in rows]}


@router.get("/student-progress")
def student_progress(user=Depends(get_user), db: Session = Depends(get_db)):
    if user["role"] != "student":
        raise HTTPException(status_code=403, detail="Student access only")

    rows = db.execute(text("""
        SELECT course_id, course_title, total_assessments,
               submitted_assessments, graded_assessments,
               average_marks, progress_percent
        FROM student_course_progress
        WHERE student_id = :student_id
        ORDER BY course_title
    """), {"student_id": user["id"]}).mappings().all()

    return {"courses": [dict(row) for row in rows]}


@router.get("/leaderboard/{course_id}")
def leaderboard(course_id: int, user=Depends(get_user), db: Session = Depends(get_db)):
    if user["role"] not in ["teacher", "admin"]:
        raise HTTPException(status_code=403, detail="Teacher or admin access only")

    rows = db.execute(text("""
        WITH student_scores AS (
            SELECT
                s.student_id,
                a.course_id,
                AVG(s.marks) AS average_marks
            FROM submissions s
            JOIN assignments a ON a.id = s.assignment_id
            WHERE a.course_id = :course_id
              AND s.marks IS NOT NULL
            GROUP BY s.student_id, a.course_id
        )
        SELECT
            ss.student_id,
            u.name,
            ROUND(ss.average_marks::numeric, 2) AS average_marks,
            RANK() OVER (ORDER BY ss.average_marks DESC) AS rank
        FROM student_scores ss
        JOIN users u ON u.id = ss.student_id
        ORDER BY rank, u.name
    """), {"course_id": course_id}).mappings().all()

    return {"course_id": course_id, "leaderboard": [dict(row) for row in rows]}
