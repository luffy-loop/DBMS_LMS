from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from models import Course, Enrollment, Assignment, Submission
from auth import get_user

router = APIRouter()

@router.get("/learning-insights")
def learning_insights(user=Depends(get_user), db: Session = Depends(get_db)):
    if user["role"] != "student":
        raise HTTPException(status_code=403, detail="Student access only")
    enrollments = db.query(Enrollment).filter(Enrollment.student_id == user["id"]).all()
    course_ids = [e.course_id for e in enrollments]
    if not course_ids:
        return {"overall": {"progress": 0, "average_marks": None, "graded": 0, "submitted": 0, "total_assessments": 0}, "courses": [], "next_actions": [{"title": "Start your learning journey", "detail": "Enroll in a course to unlock your personalized learning path.", "priority": "medium", "action": "courses"}], "focus_course": None}
    courses = {c.id: c for c in db.query(Course).filter(Course.id.in_(course_ids)).all()}
    assignments = db.query(Assignment).filter(Assignment.course_id.in_(course_ids)).all()
    submissions = db.query(Submission).filter(Submission.student_id == user["id"]).all()
    submission_map = {s.assignment_id: s for s in submissions}
    graded = [s for s in submissions if s.marks is not None]
    average_marks = round(sum(s.marks for s in graded) / len(graded), 1) if graded else None
    submitted_count = len([a for a in assignments if a.id in submission_map])
    progress = round((submitted_count / len(assignments)) * 100) if assignments else 0
    course_rows = []
    for course_id, course in courses.items():
        items = [a for a in assignments if a.course_id == course_id]
        course_submissions = [submission_map[a.id] for a in items if a.id in submission_map]
        course_graded = [s for s in course_submissions if s.marks is not None]
        avg = round(sum(s.marks for s in course_graded) / len(course_graded), 1) if course_graded else None
        course_rows.append({"id": course.id, "title": course.title, "assessments": len(items), "submitted": len(course_submissions), "graded": len(course_graded), "average_marks": avg, "progress": round((len(course_submissions) / len(items)) * 100) if items else 0})
    focus = None
    scored_courses = [c for c in course_rows if c["average_marks"] is not None]
    if scored_courses:
        focus = min(scored_courses, key=lambda c: c["average_marks"])
    else:
        pending_courses = [c for c in course_rows if c["submitted"] < c["assessments"]]
        if pending_courses:
            focus = min(pending_courses, key=lambda c: c["progress"])
    now = datetime.now()
    pending = []
    for assignment in assignments:
        if assignment.id in submission_map:
            continue
        course = courses.get(assignment.course_id)
        if not course:
            continue
        if assignment.start_time and now < assignment.start_time:
            detail = f"Opens {assignment.start_time.strftime('%d %b, %I:%M %p')}"
            priority = "medium"
        elif assignment.end_time and now >= assignment.end_time:
            continue
        else:
            detail = "Open now — complete it before the deadline."
            priority = "high"
        pending.append({"title": f"Complete {assignment.title}", "detail": f"{course.title} · {detail}", "priority": priority, "action": "assignments"})
    next_actions = sorted(pending, key=lambda x: 0 if x["priority"] == "high" else 1)[:3]
    if focus:
        if focus["average_marks"] is not None:
            next_actions.append({"title": f"Review {focus['title']}", "detail": f"Your current average is {focus['average_marks']} marks. Use AI Search to revisit the concepts behind your assessments.", "priority": "medium", "action": "search"})
        else:
            next_actions.append({"title": f"Build momentum in {focus['title']}", "detail": "Complete your first assessment to start generating personalized performance insights.", "priority": "medium", "action": "assignments"})
    if not next_actions:
        next_actions.append({"title": "Explore your course knowledge", "detail": "Use AI Search to discover relevant material from your published course resources.", "priority": "low", "action": "search"})
    return {"overall": {"progress": progress, "average_marks": average_marks, "graded": len(graded), "submitted": submitted_count, "total_assessments": len(assignments)}, "courses": course_rows, "next_actions": next_actions, "focus_course": focus}
